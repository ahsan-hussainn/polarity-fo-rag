"""The goal agent loop (ADR-0031): the model decides WHICH tools to call; code decides what may
be claimed.

Boundary, stated precisely: within a session the model plans freely -- decompose the goal, choose
tools, iterate, compare. Everything around that is deterministic and enforced in control flow:
the tool set (no path to unreleased data), the grounding set (every record a tool returned this
session -- the closed world), the output contract (the final answer arrives only through the
submit_answer tool, validated against a schema), and the release gate (_check_output): picks must
name grounded, pickable records; every stated email must belong to that record verbatim; every
pick needs evidence; confidence tiers must not exceed what fit_rank's evidence-based tier
supports where one exists. Gate failure -> one named-failure repair -> refuse with what IS known
(the ADR-0023 pattern, applied to the agent).

Every session is a run: ops.runs (kind='goal'), every model call and tool execution in
ops.run_events with tokens/USD/duration, and the full message trace -- including tool RESULTS and
any repair turn -- in ops.agent_messages (ADR-0038). The raw, unedited log the brief demands is a
database export, not a narrative.
"""
from __future__ import annotations

import json
import os
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from pipeline.agent import tools as T
from pipeline.ops import runlog as rl

AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")
MAX_STEPS = 10

SYSTEM = """You are the PolarityIQ coverage agent. You answer commercial goals about the family
offices in THIS dataset by calling tools -- never from prior knowledge. Rules you operate under
(the system also enforces them in code; violating them gets your answer rejected):
- Only records returned by your tool calls this session exist. Never name a firm or write an
  email address that did not come back from a tool.
- Per-record honesty: state how confident the fit is and WHY, citing record evidence. Where
  fit_rank says insufficient_evidence, you must not claim a confident fit -- list the firm under
  abstained with the reason, or as a weak pick with the caveat stated.
- Firms from quarantine_summary are context only: report their status honestly when coverage
  matters; never recommend them.
- TWO DIFFERENT THINGS, never conflate them. (a) RELEASE STATE: quarantined / unresolved firms were
  never released -- they are not "family offices we no longer trust", they are candidates that
  failed the inclusion standard, and many are not family offices at all. (b) TRUST STATE: a
  RELEASED record whose evidence has since moved carries trust_state='flagged' with a
  trust_reason. A question about what changed, went stale, or should be re-checked is about (b).
  Answering it with (a) is wrong and overstates decay. Use record_history for per-firm change
  history; it is the only tool that sees across cycles.
- Contact-channel honesty: PUB/A-grade email is a usable route; B is catch-all (uncertain
  delivery); no graded email means phone/LinkedIn routing. Say which applies.
- When the evidence cannot support a useful answer, say so plainly -- a short honest answer beats
  a padded one.
Domain judgment that keeps answers commercial rather than mechanical:
- AUM band filters are for goals that constrain the TARGET FIRM's size. A fund's market segment
  ("lower-middle-market", "growth") describes ITS deals, not the family office's AUM -- a large
  family office writing LP checks into a small fund is a fit, not a mismatch. Do not band FO AUM
  to the fund's deal size.
- For investor-fit goals, pass the mandate's sector/strategy words as sector_terms to fit_rank,
  and lead the verdict with the evidence picture: how many records carry stated evidence for this
  mandate, how many are plausible-but-unevidenced, and what that means for the user.
Work in steps: decompose the goal, call the tools you need (fit_rank for investor-fit goals,
structured_search for exact counts/filters, get_record to deepen, record_history for what changed
across cycles), compare, then deliver your final answer ONLY by calling submit_answer."""


class Pick(BaseModel):
    firm: str
    fit_summary: str = Field(description="why this firm, in one or two sentences, from record evidence")
    confidence: Literal["strong", "moderate", "weak"]
    evidence: list[str] = Field(min_length=1)
    caveats: list[str] = []
    outreach: Optional[str] = Field(None, description="the honest contact route and its basis")


class GoalAnswer(BaseModel):
    verdict: str = Field(description="the direct answer to the goal, 2-4 sentences")
    picks: list[Pick] = []
    abstained: list[str] = Field(default=[], description="firms/aspects where evidence is too thin, with the reason")
    coverage_note: Optional[str] = Field(None, description="what the dataset does/doesn't cover for this goal")
    next_steps: list[str] = []
    limitations: list[str] = []


# Verbs that turn "reporting on a firm" into "recommending it". Deliberately narrow: the goal is
# to catch a push to act, not to forbid naming a quarantined firm, which honest coverage requires.
_RECOMMENDS = __import__("re").compile(
    r"\b(recommend|suggest|approach|contact|reach out|pitch|target|consider|pursue|shortlist|"
    r"best fit|good fit|strong fit|worth (?:a look|approaching|contacting))\b", __import__("re").I)

_SUBMIT = {"type": "function", "function": {
    "name": "submit_answer",
    "description": "Deliver the final structured answer. This is the ONLY way to finish.",
    "parameters": GoalAnswer.model_json_schema()}}


def _free_text(ans: GoalAnswer) -> str:
    """Everything a user reads that is NOT a pick. Gated too (ADR-0039): the verdict is the first
    thing read and was entirely ungated, so an unreleasable firm could be recommended in prose
    while the picks list stayed clean."""
    return " ".join([ans.verdict or "", ans.coverage_note or ""]
                    + list(ans.abstained) + list(ans.next_steps) + list(ans.limitations))


def _check_output(ans: GoalAnswer, grounding: dict[str, dict], pickable: set[str],
                  context_only: dict[str, str] | None = None) -> list[str]:
    """Deterministic release gate over the structured answer. Returns failures (empty = pass)."""
    failures = []
    by_name = {}
    for r in grounding.values():
        nm = (r.get("family_office_name") or "").strip().lower()
        if nm:
            by_name.setdefault(nm, r)

    # 1. Free-text recommendation check. A context-only firm (quarantined / non-released, surfaced
    #    by quarantine_summary or record_history) may be REPORTED ON -- "we hold 9 quarantined
    #    firms" is honest coverage -- but must never be pushed as an action. Recommendation verbs
    #    are what separate the two, and only the system prompt was policing that.
    blob = _free_text(ans).lower()
    for crd, firm in (context_only or {}).items():
        nm = (firm or "").strip().lower()
        if len(nm) < 6 or nm not in blob:
            continue
        window_start = max(0, blob.find(nm) - 120)
        around = blob[window_start:blob.find(nm) + len(nm) + 120]
        if _RECOMMENDS.search(around):
            failures.append(
                f"free text recommends '{firm}', which the system holds but does not release "
                f"(context only); it may be reported on, never recommended")

    # 2. Emails in free text must belong to a grounded record, same rule the picks obey.
    allowed = {e.lower() for r in grounding.values()
               for e in (r.get("primary_contact_email"), r.get("secondary_contact_email")) if e}
    import re as _re2
    # rstrip('.'): the pattern's trailing [\w.]+ swallows sentence-ending punctuation, so a
    # perfectly valid "reach them at a@firm.com." would otherwise fail its own grounding check.
    for em in {m.group(0).lower().rstrip(".")
               for m in _re2.finditer(r"[\w.+-]+@[\w-]+\.[\w.]+", blob)}:
        if em not in allowed:
            failures.append(f"free text states email {em}, which is not on any retrieved record")
    for p in ans.picks:
        key = p.firm.strip().lower()
        rec = by_name.get(key)
        if rec is None:
            # Substring fallback covers stylistic name variants ("Wellspring" for "Wellspring
            # Family Office, LLC") -- but only when UNIQUE. An ambiguous partial name must fail
            # the gate rather than bind to an arbitrary record and have the email/tier checks
            # run against the wrong firm.
            subs = [r for n, r in by_name.items() if key in n or n in key]
            rec = subs[0] if len(subs) == 1 else None
        if rec is None:
            failures.append(f"pick '{p.firm}' is not a record any tool returned this session")
            continue
        if (rec.get("crd") or "") not in pickable:
            failures.append(f"pick '{p.firm}' is not releasable (non-qualifying or context-only)")
        rec_emails = {e.lower() for e in (rec.get("primary_contact_email"),
                                          rec.get("secondary_contact_email")) if e}
        text_blob = " ".join([p.fit_summary, p.outreach or ""] + p.evidence + p.caveats)
        import re as _re
        for em in _re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text_blob):
            if em.lower() not in rec_emails:
                failures.append(f"pick '{p.firm}' states email {em} which is not on that record")
        tier = rec.get("fit_confidence")
        if tier == "insufficient_evidence" and p.confidence in ("strong", "moderate"):
            failures.append(f"pick '{p.firm}' claims {p.confidence} confidence but fit_rank "
                            "measured insufficient evidence")
        if tier == "weak" and p.confidence == "strong":
            failures.append(f"pick '{p.firm}' claims strong confidence over weak measured evidence")
    return failures


def run_goal(goal: str, *, trigger: str = "api", max_steps: int = MAX_STEPS) -> dict:
    """Run one goal session. Returns {answer, verification, run_id, steps, usd}."""
    from pipeline.rag.oai import client

    run_id = rl.start_run("goal", trigger, config={"goal": goal[:500], "model": AGENT_MODEL})
    t0 = time.monotonic()
    grounding: dict[str, dict] = {}
    pickable: set[str] = set()
    context_only: dict[str, str] = {}  # crd -> firm name: visible to the model, not releasable
    seen_calls: set[tuple[str, str]] = set()  # loop-breaker: identical calls never re-execute
    messages: list[dict] = [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": f"Goal: {goal}"}]
    oai_tools = T.openai_tools() + [_SUBMIT]
    usd = 0.0
    answer: GoalAnswer | None = None
    verification = {"passed": False, "failures": [], "repaired": False}
    try:
        for step in range(1, max_steps + 1):
            t1 = time.monotonic()
            # Deterministic step governance (measured need: run 10 repeated an identical fit_rank
            # call five times and never submitted): the FINAL step may only submit.
            last = step == max_steps
            resp = client().chat.completions.create(
                model=AGENT_MODEL, temperature=0, messages=messages,
                tools=[_SUBMIT] if last else oai_tools,
                tool_choice=({"type": "function", "function": {"name": "submit_answer"}}
                             if last else "auto"))
            u = resp.usage
            step_usd = rl.usd_for(AGENT_MODEL, u.prompt_tokens, u.completion_tokens)
            usd += step_usd
            rl.event("goal", "agent_model_call", call_class="model", status="ok",
                     duration_ms=int((time.monotonic() - t1) * 1000),
                     tokens_in=u.prompt_tokens, tokens_out=u.completion_tokens, usd=step_usd,
                     detail={"step": step})
            msg = resp.choices[0].message
            messages.append({"role": "assistant", "content": msg.content,
                             "tool_calls": [tc.model_dump() for tc in (msg.tool_calls or [])] or None})
            if not msg.tool_calls:
                messages.append({"role": "user", "content":
                                 "Deliver your final answer by calling submit_answer now."})
                continue
            done = False
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name == "submit_answer":
                    try:
                        answer = GoalAnswer.model_validate(args)
                        done = True
                        messages.append({"role": "tool", "tool_call_id": tc.id,
                                         "content": "accepted"})
                    except ValidationError as ve:
                        messages.append({"role": "tool", "tool_call_id": tc.id,
                                         "content": f"schema errors, fix and resubmit: {ve.errors()[:4]}"})
                    continue
                t2 = time.monotonic()
                tool = T.TOOLS.get(name)
                if tool is None:
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": f"unknown tool {name}"})
                    continue
                call_key = (name, json.dumps(args, sort_keys=True))
                if call_key in seen_calls:
                    rl.event("goal", f"tool:{name}", call_class="retrieval", status="skipped",
                             detail={"step": step, "reason": "duplicate of an identical earlier call"})
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": "You already called this tool with identical "
                                                "arguments this session; the result is unchanged. "
                                                "Do not repeat calls -- deliver your final answer "
                                                "via submit_answer."})
                    continue
                seen_calls.add(call_key)
                try:
                    payload, recs = tool["fn"](args)
                    for r in recs:
                        crd = r.get("crd")
                        if crd:
                            # MERGE, never clobber. Different tools return different views of the
                            # same record: fit_rank carries the measured `fit_confidence` tier,
                            # get_record does not (there is no such column -- the tier is computed
                            # per mandate). `_slim` omits absent keys, so a plain assignment let a
                            # later get_record ERASE the tier, and _check_output's confidence guards
                            # read `rec.get("fit_confidence")` -> None and skipped. Measured on goal
                            # run 45: fit_rank ran once, get_record nine times on the same CRDs, and
                            # three picks shipped `strong` over records fit_rank had measured
                            # `insufficient_evidence`. A release control that silently stops applying
                            # is worse than one that is absent, because it still reports "passed".
                            # Keys present in the newer view win; keys only the older view had
                            # survive. So a re-rank under a new mandate still updates the tier, and
                            # a thin lookup can no longer disarm the gate.
                            prior = grounding.get(crd)
                            grounding[crd] = {**prior, **r} if prior else r
                            if tool["pickable"]:
                                pickable.add(crd)
                    # Firms a non-pickable tool merely EXPOSED (quarantined, non-released). The
                    # model can now see their names, so the release gate has to know them by name
                    # to police the free text -- they never enter `grounding`, which is the set of
                    # records an answer may draw evidence from.
                    if not tool["pickable"]:
                        for f in (payload.get("firms") or payload.get("flagged_records") or []):
                            if isinstance(f, dict) and f.get("crd") and f.get("firm"):
                                if f["crd"] not in pickable:
                                    context_only[f["crd"]] = f["firm"]
                    content = json.dumps(payload, default=str)[:12000]
                    status = "ok"
                except Exception as e:  # a tool failure is information, not a crash
                    content, status = f"tool error: {type(e).__name__}: {e}", "error"
                rl.event("goal", f"tool:{name}", call_class="retrieval", status=status,
                         duration_ms=int((time.monotonic() - t2) * 1000),
                         detail={"step": step, "args": args,
                                 "records": len(recs) if status == "ok" else 0})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            if done:
                break
        if answer is None:
            answer = GoalAnswer(
                verdict="The agent could not produce a grounded answer for this goal within its "
                        "step budget. No claims are made rather than unsupported ones.",
                limitations=["step budget exhausted before a valid submit_answer"])
            verification = {"passed": True, "failures": [], "repaired": False, "refused": True}
        else:
            failures = _check_output(answer, grounding, pickable, context_only)
            verification = {"passed": not failures, "failures": failures, "repaired": False}
            if failures:
                messages.append({"role": "user", "content":
                                 "Your answer FAILED the release check: " + "; ".join(failures)
                                 + ". Resubmit via submit_answer within these limits."})
                # The repair turn is a real model call and was invisible: unledgered, so its
                # tokens, cost and latency were missing and ops.runs.usd_est understated every
                # repaired session. It is also exactly the "retry" the brief asks to see.
                t_rep = time.monotonic()
                resp = client().chat.completions.create(
                    model=AGENT_MODEL, temperature=0, messages=messages, tools=[_SUBMIT])
                u = resp.usage
                repair_usd = rl.usd_for(AGENT_MODEL, u.prompt_tokens, u.completion_tokens)
                usd += repair_usd
                rl.event("goal", "agent_repair_call", call_class="model", status="ok",
                         duration_ms=int((time.monotonic() - t_rep) * 1000),
                         tokens_in=u.prompt_tokens, tokens_out=u.completion_tokens,
                         usd=repair_usd, detail={"failures": failures})
                messages.append({"role": "assistant",
                                 "content": resp.choices[0].message.content,
                                 "tool_calls": [tc.model_dump()
                                                for tc in (resp.choices[0].message.tool_calls or [])]
                                               or None})
                tc = (resp.choices[0].message.tool_calls or [None])[0]
                repaired = None
                if tc is not None and tc.function.name == "submit_answer":
                    try:
                        repaired = GoalAnswer.model_validate(json.loads(tc.function.arguments))
                    except (ValidationError, json.JSONDecodeError):
                        repaired = None
                if repaired is not None:
                    f2 = _check_output(repaired, grounding, pickable, context_only)
                    if not f2:
                        answer = repaired
                        verification = {"passed": True, "failures": [], "repaired": True}
                    else:  # still failing -> refuse, list what was grounded (never release it)
                        names = sorted({r.get("family_office_name") for r in grounding.values()
                                        if r.get("crd") in pickable})[:8]
                        answer = GoalAnswer(
                            verdict="The agent's answer failed the independent release check twice, "
                                    "so it is withheld rather than shipped unsupported.",
                            coverage_note=f"records retrieved this session: {', '.join(n for n in names if n)}",
                            limitations=[*f2])
                        verification = {"passed": False, "failures": f2, "repaired": True,
                                        "refused": True}
        outcome = "answered" if verification["passed"] and not verification.get("refused") \
            else "refused_verification"
        # ADR-0038: persist the trace BEFORE closing the run, so a session that produced an answer
        # always has its log, and so the log exists even for refusals (the most interesting case).
        traced = rl.save_messages(messages, phase="session")
        rl.log_query(source="agent", query=goal, outcome=outcome, verification=verification,
                     latency_ms=int((time.monotonic() - t0) * 1000))
        rl.finish_run("ok", summary={"goal": goal[:300], "outcome": outcome,
                                     "picks": len(answer.picks), "usd": round(usd, 5),
                                     "steps": step, "grounded_records": len(grounding),
                                     "messages_traced": traced})
        return {"answer": answer.model_dump(), "verification": verification, "run_id": run_id,
                "steps": step, "usd": round(usd, 5), "messages_traced": traced,
                "trace_note": (f"raw run log: ops.agent_messages (full message trace, incl. tool "
                               f"results and any repair turn) + ops.run_events (per-call timing, "
                               f"tokens, cost) where run_id={run_id}")}
    except Exception as e:
        # A crashed session is the one whose trace is most worth having.
        try:
            rl.save_messages(messages, phase="session")
        except Exception:
            pass
        rl.finish_run("failed", error=repr(e))
        raise

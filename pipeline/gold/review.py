"""Gate review: turn automated affirms into ratified adjudications (ADR-0029's release control).

ADR-0029 measured the gate's affirm precision at ~59% and drew the conclusion in the open: an
affirm is TRIAGE, not release. This module is the other half of that sentence -- the path by which
a triaged candidate becomes a counted record, and the only path there is.

  gate-review   -- assemble, per gate decision, everything that bears on WHAT the entity is, in the
                   ADR-0020 evidence shape (adv_item5 + website spans), alongside the gate's own
                   scored rule trail so the reviewer can see what the machine saw and where it may
                   have been credulous. Writes a sheet with a DRAFT category. A draft is a proposal.
  (human review) -- Ahsan reads the sheet, edits status/category/rationale, sets decided_by.
  gate-ratify   -- load the ratified rows into gold.entity_adjudications (refusing anything without
                   decided_by), then PROMOTE: build silver for exactly those firms and rebuild gold,
                   so a ratified firm enters the product through the standard build path.

The evidence bar is ADR-0020's, unchanged and re-enforced here: affirming needs >=2 independent
evidence classes. A row a human marks 'affirmed' on one class is loaded as 'unresolved' and
reported -- the human release control can override the gate, but not the evidence standard.

Deliberate non-feature: this module never decides. It assembles, refuses, and promotes.
"""
from __future__ import annotations

import json
import os
import re

from pipeline import db
from pipeline.curate import _SELF_DESC, _spans

SHEET = "data/curation/gate_review_sheet.json"
DECISIONS = "data/curation/gate_adjudications.json"

# The gate's three counted categories (ADR-0028) plus the outcomes a reviewer can reach instead.
COUNTED = ("single_family_office", "multi_family_office", "embedded_fo_practice")
REVIEW_CATEGORIES = COUNTED + ("ria_with_fo_practice", "wealth_manager", "not_fo", "unresolved")

_FO_PHRASE = re.compile(r"family[\s-]+office", re.I)


def _adv_evidence(cur, crd: str) -> dict | None:
    """ADR-0020 class 1: the firm's own regulatory filing. Registry-agnostic -- a candidate found
    through the state feed carries the same ADV field shape as one found through the SEC feed."""
    cur.execute("select source, raw from bronze.captures "
                "where source in ('sec_form_adv', 'state_form_adv') and entity_key = %s "
                "order by id desc limit 1", (crd,))
    row = cur.fetchone()
    if not row:
        return None
    source, raw = row
    return {"class": "adv_item5", "source_url": raw.get("source_url"),
            "observed_at": raw.get("latest_filing_date"),
            "detail": {"registry": source,
                       "hnw_clients": raw.get("hnw_clients"),
                       "nonhnw_clients": raw.get("nonhnw_clients"),
                       "hnw_raum": raw.get("hnw_raum"), "raum_total": raw.get("raum_total"),
                       "total_employees": raw.get("total_employees"),
                       "org_form": raw.get("org_form"),
                       "legal_name": raw.get("legal_name"),
                       "business_name": raw.get("business_name")}}


def _website_evidence(cur, crd: str) -> tuple[list[dict], str | None, int]:
    """ADR-0020 class 2: what the firm says it IS, as quoted spans with URL and capture date.

    Returns (evidence, strongest_category_signal, fo_phrase_count). The phrase count is reported
    because the gate's v2 self-description rule scores on it -- the reviewer should see the same
    number the machine scored, not a summary of it.
    """
    cur.execute("select raw->>'page_type', raw->>'page_url', raw->>'text', fetched_at::date "
                "from (select distinct on (raw->>'page_url') * from bronze.captures "
                "      where source = 'website' and entity_key = %s "
                "      order by raw->>'page_url', id desc) latest "
                "order by case raw->>'page_type' when 'home' then 0 when 'about' then 1 else 2 end",
                (crd,))
    ev, draft, phrases = [], None, 0
    for ptype, purl, text, fetched in cur.fetchall():
        phrases += len(_FO_PHRASE.findall(text or ""))
        for cat, pat in _SELF_DESC:
            for span in _spans(text, pat):
                ev.append({"class": "website", "source_url": purl, "observed_at": str(fetched),
                           "detail": {"page_type": ptype, "category_signal": cat, "span": span}})
                draft = draft or cat
    return ev, draft, phrases


def _latest_gate(cur, entity_key: str) -> dict | None:
    cur.execute("select gate_version, decision, category, score, evidence, contradictions, "
                "decided_at, run_id from gold.entity_gate where entity_key = %s "
                "order by decided_at desc limit 1", (entity_key,))
    r = cur.fetchone()
    if not r:
        return None
    return {"gate_version": r[0], "decision": r[1], "category": r[2], "score": r[3],
            "evidence": r[4], "contradictions": r[5], "decided_at": str(r[6]), "run_id": r[7]}


def _draft(gate: dict, web_cat: str | None, adv: dict | None, phrases: int) -> tuple[str, str]:
    """The DRAFT proposal put in front of the reviewer, plus the note that says where to look hard.

    The note's job is adversarial: it names the specific way THIS row could be the gate's ~41%
    false-affirm case, so the reviewer reads toward the weakness rather than nodding along.
    """
    cat = gate.get("category") or "unresolved"
    d = (adv or {}).get("detail") or {}
    hnw = int(d.get("hnw_clients") or 0)
    nonhnw = int(d.get("nonhnw_clients") or 0)
    total = hnw + nonhnw
    rules = {h["rule"] for h in (gate.get("evidence") or [])}
    notes = [f"gate {gate['decision']} at {gate['score']} on rules {sorted(rules)}"]

    if not gate.get("evidence"):
        notes.append("NO scored rules -- nothing affirmative was found")
    if rules == {"name_fo_strong"} or (rules <= {"name_fo_strong", "structural_fo_shape"}):
        notes.append("NAME-ONLY RISK: the affirmative evidence is essentially the firm's name; "
                     "ADR-0028 calls a marketing label without a practice non-counting")
    if not web_cat and phrases == 0:
        notes.append("no website self-description span captured -- one evidence class only, "
                     "so ADR-0020 cannot affirm this row as it stands")
    if web_cat and cat in ("multi_family_office", "single_family_office") and web_cat == "ria_with_fo_practice":
        notes.append(f"CONTRADICTION: gate says {cat}, site language says a service line "
                     "-- if it is a practice, the counted category is embedded_fo_practice")
    if cat == "multi_family_office" and total > 100:
        notes.append(f"ADV reports {total} individual clients -- retail-scale book contradicts MFO")
    if cat == "single_family_office" and total > 5:
        notes.append(f"ADV reports {total} individual clients -- contradicts a one-family claim")
    if cat == "embedded_fo_practice":
        notes.append("category 3 bar: a NAMED practice substantiated by the firm's own materials "
                     "AND a second source -- a tagline is not a practice (ADR-0028)")
    for c in gate.get("contradictions") or []:
        notes.append(f"gate contradiction {c['rule']}: {c['detail']}")
    return cat, " | ".join(notes)


def sheet(path: str = SHEET, *, decisions: tuple[str, ...] = ("affirm",),
          limit: int | None = None) -> dict:
    """Assemble the review sheet for candidates the gate has decided. Only queue rows that reached
    a gate decision appear; a candidate still pending is not review-ready."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd from gold.entity_adjudications")
        already = {r[0] for r in cur.fetchall()}
        cur.execute(
            "select entity_key, source, firm_name, detail from ops.candidate_queue "
            "where stage = 'gated' and status = 'done' order by entity_key")
        candidates = cur.fetchall()
        for entity_key, source, firm_name, detail in candidates:
            crd = entity_key.split(":", 1)[-1]
            if crd in already:
                continue
            gate = _latest_gate(cur, entity_key)
            if not gate or gate["decision"] not in decisions:
                continue
            detail = detail or {}
            adv = _adv_evidence(cur, crd)
            web_ev, web_cat, phrases = _website_evidence(cur, crd)
            draft_cat, note = _draft(gate, web_cat, adv, phrases)
            evidence = ([adv] if adv else []) + web_ev
            rows.append({
                "entity_key": entity_key, "crd": crd, "firm_name": firm_name, "source": source,
                "website": detail.get("website"), "city": detail.get("city"),
                "state": detail.get("state"),
                "gate": gate,
                "site_fo_phrase_count": phrases,
                "extracted": detail.get("extracted"),
                "evidence_classes": sorted({e["class"] for e in evidence}),
                "evidence": evidence,
                "draft_category": draft_cat, "draft_note": note,
                # what the human fills in; ratify() refuses rows without decided_by
                "category": draft_cat, "status": "unresolved", "duplicate_of": None,
                "rationale": "", "decided_by": None,
            })
    if limit:
        rows = rows[:limit]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, default=str)
    one_class = sum(1 for r in rows if len(r["evidence_classes"]) < 2)
    return {"path": path, "decisions": list(decisions), "rows": len(rows),
            "already_adjudicated": len(already),
            "cannot_affirm_on_current_evidence": one_class,
            "draft_categories": {c: sum(1 for r in rows if r["draft_category"] == c)
                                 for c in sorted({r["draft_category"] for r in rows})}}


def html_sheet(sheet_path: str = SHEET, out_path: str = "data/curation/gate_review.html") -> dict:
    """Render the review sheet as a self-contained page a human can actually work through.

    The JSON is the ratifiable artifact; this is the surface for producing it. Reviewing 20 rows of
    nested JSON in an editor is how a reviewer starts skimming, and a skimmed review of a gate whose
    measured precision is 62% is worse than no review, because it launders the gate's errors through
    a human signature. So the page leads with the adversarial note (what to disbelieve about THIS
    row), shows the evidence that decides it, and refuses to let a decision be recorded without a
    rationale in the reviewer's own words.
    """
    with open(sheet_path, encoding="utf-8") as fh:
        rows = json.load(fh)
    # Affirms first: they are the rows that would enter the product, so they get the fresh attention.
    rows.sort(key=lambda r: (r["gate"]["decision"] != "affirm", -r["gate"]["score"]))
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(_HTML.replace("__DATA__", payload).replace("__CATS__",
                 json.dumps(list(REVIEW_CATEGORIES))))
    return {"rows": len(rows), "path": out_path,
            "affirms": sum(1 for r in rows if r["gate"]["decision"] == "affirm")}


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gate review - PolarityIQ Stage 2</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#272b35;--fg:#e6e8ee;--dim:#9aa3b2;--acc:#6ea8fe;
--ok:#3fb950;--warn:#d29922;--bad:#f85149}
@media(prefers-color-scheme:light){:root{--bg:#f6f7f9;--card:#fff;--line:#e2e5ea;--fg:#1b1f27;
--dim:#5b6472;--acc:#1a63d8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;z-index:9;background:var(--bg);border-bottom:1px solid var(--line);
padding:14px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0;font-weight:650}
.sp{flex:1}
.prog{color:var(--dim);font-variant-numeric:tabular-nums}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);
color:var(--fg);border-radius:7px;padding:7px 12px}
button:hover{border-color:var(--acc)}
button.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
button:disabled{opacity:.45;cursor:not-allowed}
main{max-width:940px;margin:0 auto;padding:22px 20px 120px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:18px;margin:16px 0}
.card.done{opacity:.55}
.card.done .body{display:none}
.hd{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.nm{font-size:17px;font-weight:650}
.tag{font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--dim)}
.tag.affirm{color:var(--ok);border-color:var(--ok)}
.tag.needs_evidence{color:var(--warn);border-color:var(--warn)}
.note{margin:12px 0;padding:11px 13px;border-left:3px solid var(--warn);background:rgba(210,153,34,.09);
border-radius:0 7px 7px 0;font-size:14px}
.note b{color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:12px 0}
.f{border:1px solid var(--line);border-radius:8px;padding:9px 11px}
.f .k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim)}
.f .v{font-weight:600;font-variant-numeric:tabular-nums}
details{margin:10px 0;border:1px solid var(--line);border-radius:8px;padding:9px 11px}
summary{cursor:pointer;color:var(--dim);font-size:14px}
blockquote{margin:9px 0;padding-left:11px;border-left:2px solid var(--line);color:var(--dim);font-size:14px}
a{color:var(--acc)}
.dec{margin-top:14px;padding-top:14px;border-top:1px solid var(--line)}
.row{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
select,textarea{font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);
border-radius:7px;padding:8px}
textarea{width:100%;min-height:62px;resize:vertical}
.q{font-size:13px;padding:6px 10px}
.warn{color:var(--bad);font-size:13px;margin-top:7px}
.verdict{font-weight:650}
footer{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);
padding:12px 20px;display:flex;gap:14px;align-items:center;justify-content:center}
code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:13px}
</style></head><body>
<header><h1>Gate review</h1><span class="prog" id="prog"></span><span class="sp"></span>
<button id="dl" class="primary" disabled>Download decisions</button></header>
<main id="main"></main>
<footer><span class="prog" id="prog2"></span>
<span style="color:var(--dim);font-size:13px">save as <code>data/curation/gate_adjudications.json</code>
then run <code>python -m pipeline.cli gate-ratify --write</code></span></footer>
<script>
const ROWS=__DATA__, CATS=__CATS__;
const REVIEWER="ahsan";
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const main=document.getElementById("main");

function advBlock(r){
  const a=(r.evidence||[]).find(e=>e.class==="adv_item5"); if(!a) return "";
  const d=a.detail||{};
  const f=(k,v)=>`<div class="f"><div class="k">${k}</div><div class="v">${v==null?"&mdash;":v}</div></div>`;
  const m=n=>n==null?null:"$"+(Number(n)/1e6).toFixed(1)+"M";
  return `<div class="grid">
    ${f("HNW clients",d.hnw_clients)}${f("non-HNW clients",d.nonhnw_clients)}
    ${f("RAUM total",m(d.raum_total))}${f("HNW RAUM",m(d.hnw_raum))}
    ${f("employees",d.total_employees)}${f("registry",esc(d.registry||""))}</div>`;
}
function spans(r){
  const w=(r.evidence||[]).filter(e=>e.class==="website");
  if(!w.length) return `<div class="note"><b>No website self-description captured.</b> This row has
    ${r.evidence_classes.length} evidence class(es); ADR-0020 needs 2 to affirm, so an affirm here
    is auto-demoted to unresolved.</div>`;
  return `<details><summary>${w.length} website evidence span(s)</summary>`+
    w.map(e=>`<blockquote>&ldquo;${esc(e.detail.span)}&rdquo;<br><a href="${esc(e.source_url)}"
      target="_blank" rel="noopener">${esc(e.source_url)}</a> &middot; ${esc(e.detail.page_type)}
      &middot; signal: <code>${esc(e.detail.category_signal)}</code></blockquote>`).join("")+`</details>`;
}
function team(r){
  const t=(r.extracted&&r.extracted.team)||[];
  if(!t.length) return "";
  return `<details><summary>${t.length} people extracted</summary>`+
    t.map(p=>`<div>${esc(p.name)} &mdash; ${esc(p.title||"")}${p.principal?" <span class='tag'>principal</span>":""}</div>`).join("")+
    (r.extracted.thesis?`<blockquote>${esc(r.extracted.thesis)}</blockquote>`:"")+`</details>`;
}
function rules(g){
  return (g.evidence||[]).map(h=>`<code>${esc(h.rule)} +${h.points}</code>`).join(" ")+
    (g.contradictions||[]).map(c=>` <code style="color:var(--bad)">${esc(c.rule)} ${c.points}</code>`).join("");
}

ROWS.forEach((r,i)=>{
  const g=r.gate, thin=r.evidence_classes.length<2;
  const el=document.createElement("div"); el.className="card"; el.id="c"+i;
  el.innerHTML=`
   <div class="hd"><span class="nm">${esc(r.firm_name)}</span>
     <span class="tag ${g.decision}">gate: ${g.decision} &middot; ${g.score}</span>
     ${g.category?`<span class="tag">${esc(g.category)}</span>`:""}
     <span class="tag">CRD ${esc(r.crd)}</span>
     <span class="tag">${esc(r.city||"")} ${esc(r.state||"")}</span></div>
   <div class="body">
     <div class="note"><b>Check this:</b> ${esc(r.draft_note)}</div>
     <div style="font-size:13px;color:var(--dim)">${rules(g)}</div>
     ${r.website?`<div style="margin-top:8px"><a href="${esc(r.website)}" target="_blank" rel="noopener">${esc(r.website)}</a>
       &middot; "family office" appears <b>${r.site_fo_phrase_count}</b>&times; on site</div>`:
       `<div style="margin-top:8px;color:var(--dim)">no website</div>`}
     ${advBlock(r)} ${spans(r)} ${team(r)}
     <div class="dec">
       <div class="row">
         <button class="q" data-i="${i}" data-s="affirmed" data-c="${g.category||"multi_family_office"}">Affirm as ${esc(g.category||"MFO")}</button>
         <button class="q" data-i="${i}" data-s="affirmed" data-c="embedded_fo_practice">Affirm as embedded practice</button>
         <button class="q" data-i="${i}" data-s="rejected" data-c="wealth_manager">Reject &mdash; wealth manager</button>
         <button class="q" data-i="${i}" data-s="unresolved" data-c="unresolved">Unresolved</button>
       </div>
       <div class="row">
         <select id="st${i}"><option value="">status&hellip;</option>
           <option>affirmed</option><option>unresolved</option><option>rejected</option></select>
         <select id="ct${i}"><option value="">category&hellip;</option>
           ${CATS.map(c=>`<option>${c}</option>`).join("")}</select>
       </div>
       <textarea id="rt${i}" placeholder="Why? In your own words - this is the release decision and it is quoted in the record."></textarea>
       ${thin?`<div class="warn">Only ${r.evidence_classes.length} evidence class here - an
         &ldquo;affirmed&rdquo; will be loaded as unresolved (ADR-0020).</div>`:""}
       <div class="row" style="margin-top:10px">
         <button class="primary" data-save="${i}">Record decision</button>
         <span id="v${i}" class="verdict"></span></div>
     </div></div>`;
  main.appendChild(el);
});

function refresh(){
  const n=ROWS.filter(r=>r.decided_by).length;
  const t=`${n} / ${ROWS.length} decided`;
  prog.textContent=t; prog2.textContent=t;
  dl.disabled=n===0;
}
document.addEventListener("click",e=>{
  const q=e.target.closest("button.q");
  if(q){const i=q.dataset.i;
    document.getElementById("st"+i).value=q.dataset.s;
    document.getElementById("ct"+i).value=q.dataset.c;
    const rt=document.getElementById("rt"+i); rt.focus(); return;}
  const s=e.target.closest("button[data-save]");
  if(!s) return;
  const i=s.dataset.save, st=document.getElementById("st"+i).value,
        ct=document.getElementById("ct"+i).value, rt=document.getElementById("rt"+i).value.trim();
  const v=document.getElementById("v"+i);
  if(!st||!ct){v.textContent="pick a status and a category";v.style.color="var(--bad)";return;}
  if(!rt){v.textContent="a rationale is required";v.style.color="var(--bad)";return;}
  ROWS[i].status=st; ROWS[i].category=ct; ROWS[i].rationale=rt; ROWS[i].decided_by=REVIEWER;
  document.getElementById("c"+i).classList.add("done");
  v.textContent="recorded"; v.style.color="var(--ok)";
  refresh();
});
dl.addEventListener("click",()=>{
  const out=ROWS.filter(r=>r.decided_by);
  const b=new Blob([JSON.stringify(out,null,1)],{type:"application/json"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(b); a.download="gate_adjudications.json"; a.click();
});
refresh();
</script></body></html>
"""


def ratify(path: str = DECISIONS, *, write: bool = False, promote: bool = True) -> dict:
    """Load ratified gate reviews into gold.entity_adjudications, then promote the affirmed firms
    into the product through the standard build path.

    Refuses rows without decided_by. Affirmed rows carrying <2 evidence classes are loaded as
    'unresolved' and counted -- the human outranks the gate, never the evidence standard.
    """
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = {"file": path, "rows": len(rows), "applied": 0, "skipped_unratified": 0,
           "demoted_single_class": 0, "affirmed": 0, "written": write, "promoted": None}
    to_promote: list[str] = []
    with db.get_conn() as c, c.cursor() as cur:
        for r in rows:
            if not r.get("decided_by"):
                out["skipped_unratified"] += 1
                continue
            status, cat = r["status"], r.get("category")
            if cat not in REVIEW_CATEGORIES:
                raise ValueError(f"{r['crd']}: category {cat!r} is not one of {REVIEW_CATEGORIES}")
            if not (r.get("rationale") or "").strip():
                raise ValueError(f"{r['crd']}: a ratified row needs a rationale in plain words")
            classes = {e["class"] for e in r.get("evidence", [])}
            if status == "affirmed" and len(classes) < 2:
                status, cat = "unresolved", "unresolved"
                out["demoted_single_class"] += 1
            if status == "affirmed":
                out["affirmed"] += 1
                to_promote.append(r["crd"])
            if write:
                cur.execute(
                    "insert into gold.entity_adjudications "
                    "(crd, firm_name, category, status, duplicate_of, evidence, rationale, decided_by) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (crd) do update set "
                    "category=excluded.category, status=excluded.status, "
                    "duplicate_of=excluded.duplicate_of, evidence=excluded.evidence, "
                    "rationale=excluded.rationale, decided_by=excluded.decided_by, decided_at=now()",
                    (r["crd"], r["firm_name"], cat, status, r.get("duplicate_of"),
                     json.dumps(r.get("evidence", []), default=str), r["rationale"],
                     r["decided_by"]))
            out["applied"] += 1
        if write:
            c.commit()
    if write and promote and to_promote:
        out["promoted"] = promote_firms(to_promote, write=True)
    return out


def promote_firms(crds: list[str], *, write: bool = True) -> dict:
    """Move ratified firms into the product: extract them into silver, then rebuild gold.

    Scoped to exactly the ratified CRDs. A blanket silver rebuild would re-extract all 50 held
    records too -- extraction is not deterministic, so that would silently reword shipped cells
    (measured: a full-corpus re-extract redrafted thesis/sector text on records nobody reviewed).
    """
    from pipeline.gold import build as gb
    from pipeline.silver import load as sl

    s = sl.run(limit=None, write=write, crds=set(crds))
    g = gb.build(write=write)
    return {"requested": len(crds), "silver_firms": s["firms_processed"],
            "silver_people": s["people"], "silver_principals": s["principals"],
            "gold_firms": g.get("firms"), "written": write}

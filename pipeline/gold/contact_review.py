"""Decision-maker evidence assembly (ADR-0021/0022) — the reading done for the reviewer.

ADR-0021 requires an affirmative, evidenced decision-maker before a record carries a contact claim,
and ADR-0022 fixes how the primary is chosen: best-evidenced ALLOCATION AUTHORITY, conditioned on
entity category (SFO -> family principal; MFO / embedded practice -> CIO or head of investments),
with `stated` evidence beating `title_inferred` and reachability only a tie-breaker.

That standard is the right one and it is expensive to apply, because applying it means reading a
firm's site looking for what a named person is actually said to DO. The existing 46 adjudications
each carry a hand-written selection basis of the shape "Runs the FO day-to-day, 'actively involved
in investment strategy, asset allocation, security selection'". Nothing about that judgment is
automatable -- but almost all of the *reading* is.

So this module assembles, per candidate person, everything that bears on allocation authority:

  - the title as extracted, and where the title alone would place them (ADR-0022 ladder);
  - every sentence on the firm's captured pages that names the person, quoted with its page and
    capture date -- this is where `stated` authority evidence lives, or fails to;
  - authority verbs actually present near their name (allocates, invests, manages, oversees,
    selects, chairs) versus absent -- the difference between stated and title_inferred;
  - the affiliation-as-of date, taken from the capture that names them;
  - the email the firm publishes for them, if any, and its grade;
  - a sanity check against ADV: a firm reporting 2 employees cannot have six executives.

and an adversarial note per candidate arguing why this person may NOT hold allocation authority,
because the failure mode here is a plausible senior-sounding title shipped as a decision-maker.

The reviewer still writes `selection_basis` and decides. This module never sets `decided_by`.
"""
from __future__ import annotations

import json
import os
import re

from pipeline import db

SHEET = "data/curation/contact_review_sheet.json"
HTML = "data/curation/contact_review.html"

# Verbs that indicate the person DOES the allocating, not that they exist at the firm. Presence of
# one of these near the name is what ADR-0022 means by `stated` authority.
AUTHORITY = re.compile(
    r"\b(allocat\w+|invest\w+ (?:committee|strategy|decisions?|process)|asset allocation|"
    r"portfolio construction|security selection|manages? (?:the )?(?:portfolio|assets|investments)|"
    r"oversees? (?:the )?(?:portfolio|investments|assets)|chairs? the invest\w+|"
    r"chief investment officer|head of invest\w+|directs? (?:the )?invest\w+)\b", re.I)

# ADR-0022's category-conditioned expectation, used to flag a mismatch rather than to decide.
EXPECTED = {
    "single_family_office": "family principal or the person running the family's capital",
    "multi_family_office": "CIO / head of investments (or the founding principal if small)",
    "embedded_fo_practice": "the person who leads the family-office practice, not the firm's CEO",
}
_SENT = re.compile(r"(?<=[.!?])\s+")


def _pages(cur, crd: str) -> list[dict]:
    cur.execute(
        "select raw->>'page_type', raw->>'page_url', raw->>'text', fetched_at::date "
        "from (select distinct on (raw->>'page_url') * from bronze.captures "
        "      where source='website' and entity_key=%s order by raw->>'page_url', id desc) l "
        "order by case raw->>'page_type' when 'team' then 0 when 'about' then 1 else 2 end",
        (crd,))
    return [{"page_type": p, "url": u, "text": t, "fetched": str(f)} for p, u, t, f in cur.fetchall()]


def _is_roster(span: str, others: list[str]) -> bool:
    """True when the passage is a staff listing rather than a statement about one person.

    Length and punctuation were the obvious tests and both failed on the real data: Kelleher's
    roster spans are only 91 and 340 characters. The reliable signal is that a listing names OTHER
    people -- "Weisenfluh CEO & Founder Michael Ouellette President Neil Cataldi Managing Director"
    names three. A section heading sitting in that sequence ("Advisory Board & Investment
    Committee") predicates nothing about any of them.
    """
    low = span.lower()
    return sum(1 for o in others if o and o.lower() in low) >= 2


def _mentions(pages: list[dict], name: str, others: list[str]) -> tuple[list[dict], str | None]:
    """Every passage naming this person, quoted with page + capture date, plus the most recent
    capture date naming them -- the honest `affiliation_asof`.

    Authority is credited only from language inside the QUOTED span, never from a wider window.
    Scoring a neighbourhood while quoting a sentence is how Michael Ouellette came back flagged as
    having stated allocation authority over a span containing no authority language at all: the
    reviewer would have read the quote, seen nothing, and had to trust the flag over their own
    eyes. What is scored and what is shown must be the same text.
    """
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if len(p) > 2]
    if not parts:
        return [], None
    first, surname = parts[0], parts[-1]
    out, asof = [], None
    for pg in pages:
        text = re.sub(r"\s+", " ", pg["text"] or "")
        for sent in _SENT.split(text):
            s_low = sent.lower()
            if not (name.lower() in s_low or (surname.lower() in s_low and first.lower() in s_low)):
                continue
            span = sent.strip()[:400]
            roster = _is_roster(span, others)
            authority = bool(AUTHORITY.search(span)) and not roster
            if span and not any(o["span"] == span for o in out):
                out.append({"span": span, "page_type": pg["page_type"], "url": pg["url"],
                            "observed_at": pg["fetched"], "authority_verb": authority,
                            "roster_listing": roster})
                asof = max(asof or pg["fetched"], pg["fetched"])
    out.sort(key=lambda m: (not m["authority_verb"], m["roster_listing"], -len(m["span"])))
    return out[:6], asof


def _note(person: dict, mentions: list[dict], category: str | None, employees) -> str:
    """Adversarial note: the specific way THIS candidate could be a title mistaken for authority."""
    n = []
    stated = [m for m in mentions if m["authority_verb"]]
    rosters = [m for m in mentions if m.get("roster_listing")]
    if not mentions:
        n.append("NO passage on the firm's captured pages names this person -- the title came from "
                 "extraction alone, so there is no affiliation evidence and no authority evidence")
    elif not stated:
        detail = (f", and {len(rosters)} of them are roster listings where the name simply appears "
                  "in a staff list" if rosters else "")
        n.append(f"{len(mentions)} mention(s) but NONE state allocation authority near this "
                 f"person's name{detail} -- this would be `title_inferred`, which ADR-0022 ranks "
                 "below `stated`")
    else:
        n.append(f"{len(stated)} quoted span(s) contain allocation-authority language -- candidate "
                 "for `stated`, but read the span and confirm the sentence is about THEM and not "
                 "about the firm")
    t = (person.get("title") or "").lower()
    if any(w in t for w in ("marketing", "business development", "client service", "relationship",
                            "operations", "compliance", "counsel", "administrat")):
        n.append("TITLE IS NON-INVESTMENT: this looks like a client-facing or operational role, "
                 "which is not allocation authority however senior it sounds")
    if any(w in t for w in ("founder", "president", "ceo", "chief executive")) and category == "embedded_fo_practice":
        n.append("firm-level leader at an embedded practice: ADR-0022 wants whoever leads the FO "
                 "practice, not the firm's chief executive, unless they are the same person")
    if category and category in EXPECTED:
        n.append(f"ADR-0022 expects for {category}: {EXPECTED[category]}")
    try:
        if employees is not None and int(employees) <= 2:
            n.append(f"ADV reports {employees} employee(s) -- a roster larger than that is either "
                     "stale, aspirational, or counts contractors")
    except (TypeError, ValueError):
        pass
    if not person.get("email"):
        n.append("no published address for this person; reachability is a tie-breaker only, never "
                 "a reason to select (ADR-0022)")
    return " | ".join(n)


def sheet(path: str = SHEET, *, limit: int | None = None) -> dict:
    """Assemble contact-review rows for entity-affirmed firms that have no ratified contact yet."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    with db.get_conn() as c, c.cursor() as cur:
        cur.execute("select crd from gold.contact_adjudications where contact_role='primary'")
        done = {r[0] for r in cur.fetchall()}
        cur.execute(
            "select r.crd, r.family_office_name, r.entity_category, r.website, r.domain "
            "from gold.records r join gold.entity_adjudications a on a.crd = r.crd "
            "where a.status = 'affirmed' and a.category in "
            "  ('single_family_office','multi_family_office','embedded_fo_practice') "
            "order by r.family_office_name")
        firms = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        for f in firms:
            if f["crd"] in done:
                continue
            cur.execute("select raw->>'total_employees' from bronze.captures "
                        "where source in ('sec_form_adv','state_form_adv') and entity_key=%s "
                        "order by id desc limit 1", (f["crd"],))
            e = cur.fetchone()
            employees = e[0] if e else None
            cur.execute("select name, title, email, quality_grade, is_principal "
                        "from silver.people where firm_crd=%s order by is_principal desc, id",
                        (f["crd"],))
            people = [{"name": n, "title": t, "email": em, "grade": g, "is_principal": p}
                      for n, t, em, g, p in cur.fetchall()]
            if not people:
                continue
            pages = _pages(cur, f["crd"])
            cands = []
            names = [p["name"] for p in people]
            for p in people[:10]:
                m, asof = _mentions(pages, p["name"], [n for n in names if n != p["name"]])
                cands.append({**p, "mentions": m, "affiliation_asof": asof,
                              "has_stated_authority": any(x["authority_verb"] for x in m),
                              "note": _note(p, m, f["entity_category"], employees)})
            # Best-evidenced first: stated authority, then any mention at all.
            cands.sort(key=lambda x: (not x["has_stated_authority"], not x["mentions"]))
            rows.append({**f, "adv_employees": employees, "candidates": cands,
                         "expected_role": EXPECTED.get(f["entity_category"] or "", ""),
                         # filled by the reviewer; contact-apply refuses rows without decided_by
                         "contact_role": "primary", "name": None, "title": None,
                         "selection_basis": "", "authority_basis": None,
                         "affiliation_asof": None, "published_email": None,
                         "evidence": [], "decided_by": None})
    if limit:
        rows = rows[:limit]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, default=str)
    return {"path": path, "firms_awaiting_contact": len(rows),
            "with_a_stated_authority_candidate":
                sum(1 for r in rows if any(c["has_stated_authority"] for c in r["candidates"]))}


def html_sheet(sheet_path: str = SHEET, out_path: str = HTML) -> dict:
    """Render the contact sheet as a page the reviewer can work through. Same reasoning as the
    entity reviewer: the standard is only as good as the attention it actually receives."""
    with open(sheet_path, encoding="utf-8") as fh:
        rows = json.load(fh)
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(_HTML.replace("__DATA__", payload))
    return {"rows": len(rows), "path": out_path}


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decision-maker review - PolarityIQ Stage 2</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#272b35;--fg:#e6e8ee;--dim:#9aa3b2;--acc:#6ea8fe;
--ok:#3fb950;--warn:#d29922;--bad:#f85149}
@media(prefers-color-scheme:light){:root{--bg:#f6f7f9;--card:#fff;--line:#e2e5ea;--fg:#1b1f27;--dim:#5b6472;--acc:#1a63d8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;z-index:9;background:var(--bg);border-bottom:1px solid var(--line);
padding:14px 20px;display:flex;gap:16px;align-items:center}
h1{font-size:16px;margin:0}.sp{flex:1}.prog{color:var(--dim);font-variant-numeric:tabular-nums}
button{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--fg);
border-radius:7px;padding:7px 12px}button:hover{border-color:var(--acc)}
button.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
button:disabled{opacity:.45;cursor:not-allowed}
main{max-width:980px;margin:0 auto;padding:22px 20px 90px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:18px;margin:16px 0}
.card.done{opacity:.5}.card.done .body{display:none}
.nm{font-size:17px;font-weight:650}
.tag{font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--dim)}
.exp{margin:10px 0;font-size:14px;color:var(--dim)}
.cand{border:1px solid var(--line);border-radius:9px;padding:12px;margin:10px 0}
.cand.sel{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc) inset}
.cand .hd{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.st{color:var(--ok);font-weight:650;font-size:12px}
.ti{color:var(--warn);font-weight:650;font-size:12px}
.note{margin:9px 0;padding:9px 11px;border-left:3px solid var(--warn);background:rgba(210,153,34,.09);
border-radius:0 6px 6px 0;font-size:13px}
blockquote{margin:8px 0;padding-left:11px;border-left:2px solid var(--line);color:var(--dim);font-size:13px}
blockquote.auth{border-left-color:var(--ok);color:var(--fg)}
blockquote.roster{opacity:.6}
a{color:var(--acc)}
select,textarea,input{font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);
border-radius:7px;padding:8px}
textarea{width:100%;min-height:60px}
.row{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin:10px 0}
.dec{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.v{font-weight:650}code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:13px}
footer{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);
padding:11px 20px;display:flex;gap:14px;justify-content:center;align-items:center;font-size:13px;color:var(--dim)}
</style></head><body>
<header><h1>Decision-maker review</h1><span class="prog" id="prog"></span><span class="sp"></span>
<button id="dl" class="primary" disabled>Download decisions</button></header>
<main id="main"></main>
<footer>save as <code>data/curation/contact_adjudications.json</code> then
<code>python -m pipeline.cli contact-apply --write</code></footer>
<script>
const ROWS=__DATA__, REVIEWER="ahsan";
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const main=document.getElementById("main");
ROWS.forEach((r,i)=>{
  const el=document.createElement("div"); el.className="card"; el.id="c"+i;
  el.innerHTML=`<div><span class="nm">${esc(r.family_office_name)}</span>
    <span class="tag">${esc(r.entity_category)}</span><span class="tag">CRD ${esc(r.crd)}</span>
    <span class="tag">ADV staff ${esc(r.adv_employees)}</span></div>
   <div class="body">
   <div class="exp">ADR-0022 expects: ${esc(r.expected_role)}</div>
   ${r.candidates.map((c,j)=>`
     <div class="cand" id="p${i}_${j}">
       <div class="hd"><input type="radio" name="pick${i}" value="${j}" id="r${i}_${j}">
         <label for="r${i}_${j}"><b>${esc(c.name)}</b></label>
         <span class="tag">${esc(c.title||"no title extracted")}</span>
         <span class="${c.has_stated_authority?"st":"ti"}">${c.has_stated_authority?"STATED authority language":"title_inferred only"}</span>
         ${c.email?`<span class="tag">${esc(c.email)} · ${esc(c.grade||"ungraded")}</span>`:`<span class="tag">no published email</span>`}
         ${c.affiliation_asof?`<span class="tag">seen ${esc(c.affiliation_asof)}</span>`:""}</div>
       <div class="note">${esc(c.note)}</div>
       ${c.mentions.map(m=>`<blockquote class="${m.authority_verb?"auth":""} ${m.roster_listing?"roster":""}">
         &ldquo;${esc(m.span)}&rdquo;<br><a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.page_type)}</a>
         &middot; captured ${esc(m.observed_at)}${m.roster_listing?" &middot; <i>roster listing, not a statement</i>":""}</blockquote>`).join("")}
     </div>`).join("")}
   <div class="dec">
     <div class="row">
       <select id="ab${i}"><option value="">authority basis&hellip;</option>
         <option value="stated">stated</option><option value="title_inferred">title_inferred</option></select>
       <input id="as${i}" placeholder="affiliation as-of (e.g. team page 2026-07-28)" size="38">
       <input id="em${i}" placeholder="published email (blank if none)" size="30">
     </div>
     <textarea id="sb${i}" placeholder="selection_basis - why THIS person holds allocation authority, in your words. Quote the site if it says it."></textarea>
     <div class="row"><button class="primary" data-save="${i}">Record</button>
       <button data-skip="${i}">No provable decision-maker</button>
       <span id="v${i}" class="v"></span></div>
   </div></div>`;
  main.appendChild(el);
});
function refresh(){const n=ROWS.filter(r=>r.decided_by).length;
  prog.textContent=`${n} / ${ROWS.length} decided`; dl.disabled=n===0;}
document.addEventListener("change",e=>{
  const m=/^r(\\d+)_(\\d+)$/.exec(e.target.id||""); if(!m) return;
  const [_,i,j]=m; const r=ROWS[i], c=r.candidates[j];
  document.querySelectorAll(`#c${i} .cand`).forEach(x=>x.classList.remove("sel"));
  document.getElementById(`p${i}_${j}`).classList.add("sel");
  document.getElementById("ab"+i).value = c.has_stated_authority?"stated":"title_inferred";
  if(c.affiliation_asof) document.getElementById("as"+i).value = `${c.mentions[0]?c.mentions[0].page_type:"site"} page, captured ${c.affiliation_asof}`;
  if(c.email) document.getElementById("em"+i).value = c.email;
});
document.addEventListener("click",e=>{
  const sk=e.target.closest("button[data-skip]");
  if(sk){const i=sk.dataset.skip; const sb=document.getElementById("sb"+i).value.trim();
    const v=document.getElementById("v"+i);
    if(!sb){v.textContent="say why none of them is provable";v.style.color="var(--bad)";return;}
    ROWS[i].name=null; ROWS[i].title=null; ROWS[i].authority_basis="none";
    ROWS[i].selection_basis=sb; ROWS[i].affiliation_asof=null; ROWS[i].published_email=null;
    ROWS[i].evidence=[]; ROWS[i].decided_by=REVIEWER;
    document.getElementById("c"+i).classList.add("done");
    v.textContent="recorded: no provable decision-maker"; v.style.color="var(--warn)"; refresh(); return;}
  const s=e.target.closest("button[data-save]"); if(!s) return;
  const i=s.dataset.save, v=document.getElementById("v"+i);
  const picked=document.querySelector(`input[name=pick${i}]:checked`);
  const ab=document.getElementById("ab"+i).value, as=document.getElementById("as"+i).value.trim(),
        sb=document.getElementById("sb"+i).value.trim(), em=document.getElementById("em"+i).value.trim();
  if(!picked){v.textContent="pick a person, or use 'no provable decision-maker'";v.style.color="var(--bad)";return;}
  if(!ab||!as||!sb){v.textContent="authority basis, affiliation as-of and selection basis are all required";
    v.style.color="var(--bad)";return;}
  const c=ROWS[i].candidates[picked.value];
  ROWS[i].name=c.name; ROWS[i].title=c.title; ROWS[i].authority_basis=ab;
  ROWS[i].affiliation_asof=as; ROWS[i].selection_basis=sb; ROWS[i].published_email=em||null;
  ROWS[i].evidence=c.mentions.map(m=>({axis:"authority",observed:m.span,source_url:m.url,
    observed_at:m.observed_at,roster_listing:!!m.roster_listing}));
  ROWS[i].decided_by=REVIEWER;
  document.getElementById("c"+i).classList.add("done");
  v.textContent="recorded"; v.style.color="var(--ok)"; refresh();
});
dl.addEventListener("click",()=>{
  const out=ROWS.filter(r=>r.decided_by).map(r=>({crd:r.crd,contact_role:"primary",name:r.name,
    title:r.title,selection_basis:r.selection_basis,authority_basis:r.authority_basis,
    affiliation_asof:r.affiliation_asof,published_email:r.published_email,
    evidence:r.evidence,decided_by:r.decided_by}));
  const b=new Blob([JSON.stringify(out,null,1)],{type:"application/json"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(b);
  a.download="contact_adjudications.json"; a.click();
});
refresh();
</script></body></html>
"""

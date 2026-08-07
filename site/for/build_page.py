#!/usr/bin/env python3
"""Build a pre-baked, per-prospect Icarus page from real pipeline output.

One page per cold-email prospect: their repo, real questions, the real answers
Icarus gave, real citations linking into their own GitHub. No auth, no backend,
no model call at view time -- so the link in the email opens instantly, costs
nothing per click, and cannot be abused.

Input is the JSON written by asking `GatedPipeline.answer()` a list of
questions (list of {question, verdict, answer, citations, retrieved}) plus the
corpus's own meta.json for repo/commit provenance.

    python3 site/for/build_page.py <answers.json> <meta.json> <out.html>

Answers are rendered verbatim. Nothing here rewrites, softens, or hand-edits a
model output -- an unknown renders AS an unknown, which is the point of the
page. Order: strongest answer first, then the honest unknowns, then the rest,
because the unknowns are the part no competitor's demo will show.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from demo.links import ref_to_url  # the product's own citation->URL mapping

def order_rows(answers):
    """Strongest answer first, then the first honest unknown, then input order.

    Deliberately not per-prospect hand-picking: the second slot is always an
    abstention, because that is the part of the page no competitor's demo will
    show. "Strongest" prefers an answer that NAMES A CODE SYMBOL (a `backticked`
    identifier), falling back to length -- measured on the first two prospects,
    length alone led Cap with a permissions answer over the one identifying
    `SCShareableContent` as the leak, which is the answer that proves
    comprehension.
    """
    answered = [r for r in answers if r["verdict"] == "answer" and r.get("citations")]
    unknown = [r for r in answers if r not in answered]
    lead = max(answered, default=None,
               key=lambda r: ("`" in r["answer"], len(r["answer"])))
    head = [r for r in (lead, unknown[0] if unknown else None) if r is not None]
    return head + [r for r in answers if r not in head]

CSS = """
:root{--paper:#F7F6F2;--card:#FFF;--ink:#16181D;--muted:#6B7280;--line:#16181D;
--hair:#E4E2DB;--accent:#2F6BFF;--grounded:#0F7B53;--unknown:#9A6B00;
--mono:"Berkeley Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--sans);}
.wrap{max-width:820px;margin:0 auto;padding:44px 24px 90px;}
.brand{display:flex;align-items:center;gap:9px;font-weight:650;font-size:18px;margin-bottom:26px;}
.mark{display:inline-flex;align-items:flex-end;gap:2px;height:22px;}
.mark i{width:3px;background:var(--ink);border-radius:1px;}
.mark .b1{height:11px}.mark .b2{height:18px}.mark .stem{height:22px;background:var(--accent)}
.mark .b4{height:14px}.mark .b5{height:8px}
h1{font-size:27px;font-weight:650;margin:0 0 6px;letter-spacing:-.01em;}
h1 .repo{font-family:var(--mono);font-size:24px;}
.sub{color:var(--muted);font-size:14px;margin:0 0 22px;}
.panel{border:1.5px solid var(--line);border-radius:4px;background:#fff;padding:14px 16px;margin:0 0 30px;}
.panel .row{font:12px var(--mono);margin:0 0 7px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;}
.panel .row:last-child{margin-bottom:0}
.tag{font:600 10px var(--sans);letter-spacing:.08em;text-transform:uppercase;color:#fff;
background:var(--ink);padding:1px 6px;border-radius:3px;flex:none;}
.tag.ok{background:var(--grounded)}
.label{font:600 11px var(--sans);letter-spacing:.10em;text-transform:uppercase;margin:0 0 10px;color:var(--muted);}
details{border:1.5px solid var(--line);border-radius:4px;background:var(--card);
box-shadow:5px 5px 0 var(--line);margin:0 0 18px;}
details[data-verdict="unknown"]{background:#FBF7EC}
summary{cursor:pointer;list-style:none;padding:17px 20px;font-size:17px;font-weight:600;
display:flex;gap:12px;align-items:flex-start;}
summary::-webkit-details-marker{display:none}
summary:hover{background:#EFEEE8}
details[data-verdict="unknown"] summary:hover{background:#F6EFDF}
.pill{font:600 10px var(--sans);letter-spacing:.08em;text-transform:uppercase;flex:none;
padding:3px 7px;border-radius:3px;border:1.5px solid var(--grounded);color:var(--grounded);margin-top:3px;}
.pill.unknown{border-color:var(--unknown);color:var(--unknown)}
.body{padding:0 20px 20px;border-top:1.5px solid var(--hair);}
.prose{font-size:17px;line-height:1.6;margin:16px 0 18px;white-space:pre-wrap;}
.prose code{font-family:var(--mono);font-size:.92em;background:#EFEEE8;padding:1px 5px;border-radius:3px;}
.hero{font-size:26px;font-weight:650;margin:16px 0 8px;line-height:1.2;}
.heronote{color:var(--muted);font-size:14px;margin:0 0 16px;max-width:540px;}
.cites{display:flex;flex-wrap:wrap;gap:8px;}
.chip{display:inline-flex;align-items:center;gap:7px;font-family:var(--mono);font-size:13px;
border:1.5px solid var(--line);border-radius:4px;padding:5px 10px;background:#fff;
color:var(--ink);text-decoration:none;}
.chip:hover{box-shadow:2px 2px 0 var(--accent)}
.chip .src{font:600 10px var(--sans);letter-spacing:.08em;text-transform:uppercase;color:#fff;
background:var(--ink);padding:1px 5px;border-radius:3px;}
.chip.pr .src{background:var(--accent)}.chip.issue .src{background:var(--unknown)}
.chip.code .src,.chip.doc .src,.chip.config .src{background:var(--grounded)}
.chip.commit .src{background:#5B4B8A}
.searched{border:1.5px solid var(--line);border-radius:4px;background:#fff;padding:12px 14px;}
.searched .k{font:600 11px var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.06em;}
.searched .v{font-family:var(--mono);font-size:12.5px;margin-top:7px;line-height:1.9;word-break:break-word;}
.ask{margin-top:34px;border-top:1.5px solid var(--hair);padding-top:26px;}
.askrow{display:flex;gap:10px;}
.askrow input{flex:1;padding:13px 15px;border:1.5px solid var(--line);border-radius:4px;
background:#fff;font-size:16px;font-family:var(--sans);color:var(--muted);}
.askrow button{padding:13px 22px;border:1.5px solid var(--line);border-radius:4px;
background:var(--accent);color:#fff;font-weight:650;font-size:15px;box-shadow:3px 3px 0 var(--line);}
.askrow input:disabled,.askrow button:disabled{opacity:.55}
.asknote{font-size:14px;color:var(--muted);margin:12px 0 0;}
footer{margin-top:40px;border-top:1.5px solid var(--hair);padding-top:16px;
font-size:13px;color:var(--muted);line-height:1.7;}
@media (max-width:560px){.wrap{padding:28px 16px 70px}h1{font-size:22px}h1 .repo{font-size:18px}}
"""

MARK = ('<span class="mark"><i class="b1"></i><i class="b2"></i><i class="stem"></i>'
        '<i class="b4"></i><i class="b5"></i></span>')


def chip(ref, repo, commit):
    source = ref.partition(":")[0]
    url = ref_to_url(ref, repo, commit)
    shown = ref.partition(":")[2]
    if source == "commit":
        shown = shown[:7]
    inner = (f'<span class="src">{html.escape(source)}</span>'
             f'<span>{html.escape(shown)}</span>')
    if url is None:
        return f'<span class="chip {html.escape(source)}">{inner}</span>'
    return (f'<a class="chip {html.escape(source)}" href="{html.escape(url)}" '
            f'target="_blank" rel="noopener">{inner}</a>')


def prose(text):
    """Escape the model's answer, then render its markdown code spans.

    The writer emits `Identifier` backticks; showing them raw looks unfinished
    on a page a stranger judges you by. Escaping happens FIRST, so nothing
    inside the answer can inject markup.
    """
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text))


def render_row(row, repo, commit):
    q = html.escape(row["question"])
    known = row["verdict"] == "answer" and row.get("citations")
    if known:
        pill = '<span class="pill">answered</span>'
        cites = "".join(chip(r, repo, commit) for r in row["citations"])
        body = (f'<p class="prose">{prose(row["answer"])}</p>'
                f'<p class="label">Evidence</p><div class="cites">{cites}</div>')
    else:
        pill = '<span class="pill unknown">unknown</span>'
        searched = "<br>".join(html.escape(r) for r in row.get("retrieved", [])[:8])
        body = ('<p class="hero">No one wrote this down.</p>'
                '<p class="heronote">Icarus found no recorded reason, so it did not invent '
                'one. This is the whole point: it answers from evidence or it abstains.</p>'
                f'<div class="searched"><div class="k">What it searched</div>'
                f'<div class="v">{searched}</div></div>')
    return (f'<details data-verdict="{"answer" if known else "unknown"}">'
            f'<summary>{pill}<span>{q}</span></summary>'
            f'<div class="body">{body}</div></details>')


def build(answers, meta):
    repo, commit = meta["repo"], meta["commit"]
    c = meta["counts"]
    rows = order_rows(answers)
    counted = "  ·  ".join(f"{c[k]:,} {k}" for k in
                           ("pr", "issue", "commit", "code", "doc", "config") if c.get(k))
    answered = sum(1 for r in answers if r["verdict"] == "answer" and r.get("citations"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Icarus on {html.escape(repo)}</title>
<meta name="robots" content="noindex">
<style>{CSS}</style></head><body><div class="wrap">
<div class="brand">{MARK}<span>Icarus</span></div>
<h1>Icarus, reading <span class="repo">{html.escape(repo)}</span></h1>
<p class="sub">Real questions, answered from your own repository. Every answer links to the
evidence it used. {answered} of {len(answers)} were answerable — the rest say so.</p>
<div class="panel">
  <div class="row"><span class="tag ok">indexed</span><span>{html.escape(counted)}</span></div>
  <div class="row"><span class="tag">commit</span><span>{html.escape(commit[:12])}</span></div>
</div>
<p class="label">Questions a new contributor would ask</p>
{"".join(render_row(r, repo, commit) for r in rows)}
<div class="ask">
  <div class="askrow">
    <input disabled placeholder="Ask something else about {html.escape(repo)}…">
    <button disabled>Ask</button>
  </div>
  <p class="asknote">This page is pre-computed, so it opens instantly and costs you nothing.
  Reply to my email and I&rsquo;ll open a live session against your repo where you can
  ask it anything.</p>
</div>
<footer>
Answers on this page are unedited output from the same pipeline the product runs —
retrieve, cite-or-abstain, then a deterministic gate that drops any answer whose citations
aren&rsquo;t genuinely retrieved. Nothing here was written by hand.<br>
Your code was read to answer these questions and discarded. It was not used for training.
</footer>
</div></body></html>
"""


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    answers = json.loads(Path(sys.argv[1]).read_text())
    meta = json.loads(Path(sys.argv[2]).read_text())
    out = Path(sys.argv[3])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(answers, meta))
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")

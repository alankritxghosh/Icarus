"""One table of every lead ever screened. Regenerated from what is on disk.

    python3 sales/roll_up.py

Reads outputs/leads/candidates-*.json (stage 1), fit.json (stage 2 signals)
and *-answers.json (stage 3), and writes outputs/leads/ALL_LEADS.md.

Holds no state of its own: delete ALL_LEADS.md and it rebuilds identically.
A signal that was never measured prints as "-", never as a guess.
"""

import json
from pathlib import Path

LEADS = Path(__file__).resolve().parent.parent / "outputs" / "leads"


def load_leads():
    """repo -> row, newest screening wins on the fields it provides."""
    rows = {}
    for f in sorted(LEADS.glob("candidates-*.json")):
        day = f.stem.replace("candidates-", "")
        d = json.loads(f.read_text())
        for r in d.get("passed", []):
            rows.setdefault(r["repo"], {}).update({
                "repo": r["repo"], "stars": r["stars"], "seen": day,
                "query": d.get("query", ""),
                "contact": next((f"{c['name'] or c['login']} <{c['email']}>"
                                 for c in r["contacts"]), ""),
            })
    return rows


def attach_fit(rows):
    fit = LEADS / "fit.json"
    if not fit.exists():
        return
    for repo, f in json.loads(fit.read_text()).items():
        rows.setdefault(repo, {"repo": repo})["fit"] = f


def attach_answers(rows):
    for f in LEADS.glob("*-answers.json"):
        repo = f.stem.replace("-answers", "").replace("__", "/")
        results = json.loads(f.read_text())
        row = rows.setdefault(repo, {"repo": repo})
        row["asked"] = len(results)
        row["history"] = sum(1 for r in results if r.get("grade") == "HISTORY")
        row["doc_only"] = sum(1 for r in results if r.get("grade") == "doc-only")
        row["unknown"] = sum(1 for r in results if r.get("grade") == "unknown")


def status(row):
    """Where this lead is, derived -- never stored, so it cannot go stale."""
    if row.get("asked"):
        return "READY TO RECORD" if row.get("history", 0) >= 10 else "asked, weak"
    if (LEADS / "corpora" / row["repo"].replace("/", "__") / "chunks.jsonl").exists():
        return "indexed"
    if not row.get("contact"):
        return "no contact"
    return "screened"


def render(rows):
    order = {"READY TO RECORD": 0, "asked, weak": 1, "indexed": 2,
             "screened": 3, "no contact": 4}
    ranked = sorted(rows.values(),
                    key=lambda r: (order[status(r)], -(r.get("history") or 0),
                                   -((r.get("fit") or {}).get("human_prs") or 0)))
    out = ["# All leads", "",
           f"{len(ranked)} repos screened. Regenerate with `python3 sales/roll_up.py`.", "",
           "| repo | status | answers (history/doc/unknown) | human PRs | contributors | stars | contact | first seen |",
           "|---|---|---|---|---|---|---|---|"]
    for r in ranked:
        fit = r.get("fit") or {}
        answers = (f"{r['history']}/{r['doc_only']}/{r['unknown']} of {r['asked']}"
                   if r.get("asked") else "-")
        out.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["repo"], status(r), answers,
            fit.get("human_prs", "-"), fit.get("contributors", "-"),
            r.get("stars", "-"), r.get("contact") or "-", r.get("seen", "-")))
    out += ["", "Per-repo detail: `briefing-<date>.md`, `<owner>__<repo>-answers.json`."]
    return "\n".join(out) + "\n"


def people():
    """login -> the person, and every screened repo they can merge in.

    Person-centric, unlike `load_leads`, which is repo-centric and keeps only
    the first contact. One human maintaining four repos is ONE person to
    email, not four -- counting rows instead of people is how a "100 leads"
    list turns out to be sixty humans.

    Everyone here already passed `screen_leads.write_access`, so presence in
    this table means proven commit rights, not merely activity.
    """
    who = {}
    for f in sorted(LEADS.glob("candidates*.json")):
        for r in json.loads(f.read_text()).get("passed", []):
            for c in r.get("contacts", []):
                p = who.setdefault(c["login"], {
                    "login": c["login"], "name": c.get("name"),
                    "email": c["email"], "company": c.get("company"),
                    "repos": [], "merges": 0,
                })
                if r["repo"] not in p["repos"]:
                    p["repos"].append(r["repo"])
                p["merges"] = max(p["merges"], c.get("merges") or 0)
    return who


def render_people(who):
    ranked = sorted(who.values(), key=lambda p: (-p["merges"], p["login"].lower()))
    out = ["# Verified owners", "",
           f"**{len(ranked)} distinct humans**, each with PROVEN commit rights on at "
           "least one screened repo. Regenerate with `python3 sales/roll_up.py`.", "",
           "Every row satisfies both list-quality gates: a named human (never a role",
           "address, never a bot) who has merged pull requests there, or owns the",
           "repo personally. `merges` is capped by the 100-PR sample, so 125 means",
           "\"merged every pull request looked at\" -- a floor, not a lifetime count.", "",
           "| person | email | merges | repos they can merge in |",
           "|---|---|---|---|"]
    for p in ranked:
        out.append("| {} | {} | {} | {} |".format(
            p["name"] or p["login"], p["email"], p["merges"] or "-",
            ", ".join(p["repos"][:3]) + (" +%d" % (len(p["repos"]) - 3)
                                         if len(p["repos"]) > 3 else "")))
    out += ["", "Contacts that FAILED the authority check are kept per-repo under",
            "`contacts_no_write` in the candidates files -- dropped, never deleted."]
    return "\n".join(out) + "\n"


def self_check():
    one = {"passed": [{"repo": "a/b", "contacts": [
        {"login": "maria", "name": "Maria", "email": "m@x.io", "merges": 12}]}]}
    two = {"passed": [{"repo": "c/d", "contacts": [
        {"login": "maria", "name": "Maria", "email": "m@x.io", "merges": 3}]}]}
    who = {}
    for d in (one, two):                      # simulate two candidates files
        for r in d["passed"]:
            for c in r["contacts"]:
                p = who.setdefault(c["login"], {**c, "repos": [], "merges": 0})
                p["repos"].append(r["repo"])
                p["merges"] = max(p["merges"], c["merges"])
    assert len(who) == 1, "one human on two repos is ONE person"
    assert who["maria"]["repos"] == ["a/b", "c/d"]
    assert who["maria"]["merges"] == 12, "keeps the strongest authority signal"
    assert "Maria" in render_people(who) and "m@x.io" in render_people(who)
    assert "1 distinct humans" in render_people(who)

    rows = {"a/b": {"repo": "a/b", "contact": "x <x@y.z>", "asked": 20,
                    "history": 19, "doc_only": 0, "unknown": 1}}
    assert status(rows["a/b"]) == "READY TO RECORD"
    assert status({"repo": "a/b", "contact": "x", "asked": 5, "history": 2}) == "asked, weak"
    assert status({"repo": "no/such", "contact": ""}) == "no contact"
    assert status({"repo": "no/such", "contact": "x"}) == "screened"
    assert "a/b" in render(rows)
    print("self-check ok")


if __name__ == "__main__":
    import sys
    if "--self-check" in sys.argv:
        self_check()
    else:
        rows = load_leads()
        attach_fit(rows)
        attach_answers(rows)
        (LEADS / "ALL_LEADS.md").write_text(render(rows))
        print(f"{len(rows)} leads -> {LEADS / 'ALL_LEADS.md'}")
        who = people()
        (LEADS / "VERIFIED_OWNERS.md").write_text(render_people(who))
        print(f"{len(who)} verified owners -> {LEADS / 'VERIFIED_OWNERS.md'}")

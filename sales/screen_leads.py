"""Stage 1 of the lead pipeline: screen GitHub repos, find a named human.

Sales tooling. Imports nothing from evals/ or demo/ and never touches a
corpus -- this is not part of the Icarus product.

Deterministic on purpose: every gate here is a number or a string match, so
it cannot invent a repo, a person, or an address.

    python3 sales/screen_leads.py "topic:video-editing stars:>500" --limit 50
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MIN_SIZE_KB = 5000          # ~5MB: below this the public repo is an SDK, not the product
MIN_TS_SHARE = 0.50         # measured strength: ts_chunk took tsx recall 66.7% -> 100%
MAX_STARS = 50_000          # above this the email drowns in inbound
MAX_PUSH_AGE_DAYS = 60

# bots that register as type "User" and so survive the type check
BOT_LOGINS = {"renovate-bot", "renovate", "dependabot", "greenkeeper",
              "allcontributors", "github-actions", "web-flow", "semantic-release"}

# Service accounts hold write access legitimately, so the merge check PROVES
# their permission and says nothing about whether they are a person. Found
# live 2026-08-17: `svc-cli-bot <Svc_cli_bot@salesforce.com>` topped oclif.
# Matched on a WORD boundary so real humans survive -- "Botond", "abbot",
# "robota" must not be filtered.
BOT_PATTERN = re.compile(r"(^|[-_.])(bot|bots|svc|service|ci|automation)([-_.]|$)", re.I)


def is_bot(login):
    """True for a login that is machinery rather than a person."""
    if not login:
        return True
    return (login.endswith("[bot]")
            or login.lower() in BOT_LOGINS
            or bool(BOT_PATTERN.search(login)))

# A personal repo's owner outranks any merger on it. Weighted rather than
# forced to the top so a genuinely absent owner still loses to whoever is
# actually merging -- ownership is authority, activity is who to talk to.
OWNER_WEIGHT = 25

ROLE_INBOXES = {
    "founders", "founder", "info", "hello", "hi", "support", "sales",
    "hiring", "contact", "team", "admin", "help", "press", "careers",
    "jobs", "security", "noreply", "no-reply", "mail", "office", "enquiries",
}


def gh(path, *args):
    """One `gh api` call. Returns parsed JSON, or None if gh refused."""
    out = subprocess.run(
        ["gh", "api", path, *args], capture_output=True, text=True, timeout=60
    )
    if out.returncode != 0:
        print(f"  gh api {path} failed: {out.stderr.strip()[:120]}", file=sys.stderr)
        return None
    return json.loads(out.stdout)


def ts_share(languages):
    """Fraction of bytes that are TypeScript or JavaScript."""
    total = sum(languages.values())
    if not total:
        return 0.0
    ts = sum(v for k, v in languages.items() if k in ("TypeScript", "JavaScript"))
    return ts / total


def failed_gates(repo, languages, now):
    """Every reason this repo is not worth indexing. Empty list == it passes."""
    reasons = []
    if repo["size"] < MIN_SIZE_KB:
        reasons.append(f"too small ({repo['size']}KB < {MIN_SIZE_KB}KB)")
    share = ts_share(languages)
    if share < MIN_TS_SHARE:
        reasons.append(f"not TS-dominant ({share:.0%} < {MIN_TS_SHARE:.0%})")
    if repo["stargazers_count"] > MAX_STARS:
        reasons.append(f"too famous ({repo['stargazers_count']} stars)")
    pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    age = (now - pushed).days
    if age > MAX_PUSH_AGE_DAYS:
        reasons.append(f"stale (last push {age}d ago)")
    if repo.get("archived"):
        reasons.append("archived")
    return reasons


def usable_email(email):
    """A profile-published address we may write to, or None.

    GitHub's noreply address does not receive mail and is an explicit opt-out.
    A role inbox is banned outright -- batch 1 sent 20 of 23 to one.
    """
    if not email or "@" not in email:
        return None
    local, _, domain = email.partition("@")
    if domain.endswith("users.noreply.github.com"):
        return None
    if local.lower() in ROLE_INBOXES:
        return None
    return email


_AUTHORITY_QUERY = """query($owner:String!,$name:String!,$n:Int!){
  repository(owner:$owner,name:$name){
    owner{ __typename login }
    pullRequests(states:MERGED, first:$n,
                 orderBy:{field:UPDATED_AT,direction:DESC}){
      nodes{ mergedBy{ login } }
    }
  }
}"""


def _authority_from(payload):
    """Logins with PROVEN write access -> how many merges prove it.

    Merging a pull request REQUIRES write access, so `mergedBy` is a fact
    about permission. Contribution count is not: it is the number of patches
    someone got accepted, which is exactly what a contributor with no rights
    also has. Sourcing contacts from `/contributors` is why campaign 3 emailed
    a marp-cli contributor who replied "I'm just a contributor so not for me".

    A personal repo's owner always has write access to it, so they count
    without needing a merge. An ORGANISATION does not -- it is not a person to
    email -- so an org-owned repo must produce a real merger or nothing.

    Self-merges count. Merging your own pull request still requires the right
    to merge, which is the only thing being claimed here.
    """
    repo = (payload or {}).get("data", {}).get("repository") or {}
    counts = {}
    for node in (repo.get("pullRequests") or {}).get("nodes") or []:
        who = (node or {}).get("mergedBy") or {}
        login = who.get("login", "")
        if is_bot(login):
            continue
        counts[login] = counts.get(login, 0) + 1
    owner = repo.get("owner") or {}
    if owner.get("__typename") == "User":
        login = owner.get("login", "")
        if not is_bot(login):
            counts.setdefault(login, 0)
            counts[login] += OWNER_WEIGHT
    return counts


def write_access(full_name, sample=100):
    """Ask GitHub who actually merges here. One GraphQL call per repo."""
    owner, _, name = full_name.partition("/")
    payload = gh("graphql", "-f", f"query={_AUTHORITY_QUERY}",
                 "-F", f"owner={owner}", "-F", f"name={name}",
                 "-F", f"n={sample}")
    return _authority_from(payload)


def contacts(full_name, per_repo=4):
    """Named humans with proven commit rights AND a usable public address.

    Ranked by merges, so the first contact is the person doing the most
    merging -- the closest public proxy for "the maintainer" this can get
    without asking them.
    """
    authority = write_access(full_name)
    found = []
    for login, merges in sorted(authority.items(), key=lambda kv: -kv[1]):
        if len(found) >= per_repo:
            break
        u = gh(f"users/{login}")
        if not u or u.get("type") != "User":
            continue
        email = usable_email(u.get("email"))
        if email:
            found.append({
                "login": login, "name": u.get("name"), "email": email,
                "company": u.get("company"), "blog": u.get("blog"),
                "merges": merges,
            })
    return found


def screen(query, limit, now=None):
    now = now or datetime.now(timezone.utc)
    found = gh(
        "search/repositories", "-X", "GET", "-f", f"q={query}",
        "-f", "sort=stars", "-f", f"per_page={min(limit, 100)}",
    )
    if not found:
        return [], []
    passed, rejected = [], []
    for repo in found["items"][:limit]:
        languages = gh(f"repos/{repo['full_name']}/languages") or {}
        reasons = failed_gates(repo, languages, now)
        if reasons:
            rejected.append({"repo": repo["full_name"], "reasons": reasons})
            continue
        people = contacts(repo["full_name"])
        row = {
            "repo": repo["full_name"],
            "owner": repo["owner"]["login"],
            "url": repo["html_url"],
            "description": repo.get("description"),
            "stars": repo["stargazers_count"],
            "size_kb": repo["size"],
            "ts_share": round(ts_share(languages), 3),
            "pushed_at": repo["pushed_at"],
            "contacts": people,
        }
        if people:
            passed.append(row)
        else:
            rejected.append({"repo": repo["full_name"],
                             "reasons": ["nobody with proven commit rights "
                                         "publishes a usable address"]})
    return passed, rejected


def self_check():
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    fresh = (now - timedelta(days=3)).isoformat().replace("+00:00", "Z")
    ok = {"size": 9000, "stargazers_count": 2000, "pushed_at": fresh}
    ts = {"TypeScript": 800, "Rust": 200}

    assert failed_gates(ok, ts, now) == []
    assert "too small" in failed_gates({**ok, "size": 400}, ts, now)[0]
    assert "not TS-dominant" in failed_gates(ok, {"Rust": 1000}, now)[0]
    assert "too famous" in failed_gates({**ok, "stargazers_count": 129_000}, ts, now)[0]
    stale = (now - timedelta(days=400)).isoformat().replace("+00:00", "Z")
    assert "stale" in failed_gates({**ok, "pushed_at": stale}, ts, now)[0]
    assert failed_gates({**ok, "archived": True}, ts, now) == ["archived"]
    assert ts_share({}) == 0.0

    assert usable_email("steve@tldraw.com") == "steve@tldraw.com"
    assert usable_email("1234+richie@users.noreply.github.com") is None
    assert usable_email("hello@cap.so") is None
    assert usable_email("Founders@acme.io") is None
    assert usable_email(None) is None
    assert usable_email("garbage") is None

    # Authority: the campaign-3 defect. A contributor is not a maintainer.
    def payload(nodes, owner_type="Organization", owner_login="acme"):
        return {"data": {"repository": {
            "owner": {"__typename": owner_type, "login": owner_login},
            "pullRequests": {"nodes": nodes}}}}

    merged = [{"mergedBy": {"login": "maria"}}, {"mergedBy": {"login": "maria"}},
              {"mergedBy": {"login": "sam"}}]
    a = _authority_from(payload(merged))
    assert a == {"maria": 2, "sam": 1}, a
    # ranked by merges, so the first contact is the one doing the merging
    assert max(a, key=a.get) == "maria"

    # a contributor who never merged anything is absent, not ranked last
    assert "chris" not in _authority_from(payload(merged))

    # an unmerged PR proves nothing; nor does a bot merge
    assert _authority_from(payload([{"mergedBy": None}])) == {}
    assert _authority_from(payload([{"mergedBy": {"login": "dependabot"}}])) == {}
    assert _authority_from(payload([{"mergedBy": {"login": "some[bot]"}}])) == {}
    # a service account with REAL write access -- found live on oclif
    assert _authority_from(payload([{"mergedBy": {"login": "svc-cli-bot"}}])) == {}
    assert is_bot("svc-cli-bot") and is_bot("github-actions") and is_bot("ci_runner")
    # ...but a person whose name merely contains those letters must survive
    for human in ("Botond", "abbot", "robota", "Cicero", "svcnik", "ServiceNowDev"):
        assert not is_bot(human), human
    # A BARE "service"/"ci"/"bot" login is filtered on purpose -- an account
    # named only that is not a person. The boundary is what protects "Botond".
    assert is_bot("service") and is_bot("ci") and is_bot("bot")

    # a personal repo's owner has write access without merging anything
    owned = _authority_from(payload([], "User", "boris"))
    assert owned == {"boris": OWNER_WEIGHT}, owned
    # ...and outranks a mere merger on their own repo
    both = _authority_from(payload(merged, "User", "sam"))
    assert max(both, key=both.get) == "sam", both
    # an ORGANISATION is not a person to email
    assert _authority_from(payload([], "Organization", "acme")) == {}

    # hostile / empty input must not raise
    assert _authority_from({}) == {}
    assert _authority_from(None) == {}
    assert _authority_from({"data": {"repository": None}}) == {}
    print("self-check ok")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", nargs="?", help="GitHub repo search query")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--out", default="outputs/leads/candidates.json")
    p.add_argument("--self-check", action="store_true")
    a = p.parse_args()

    if a.self_check:
        return self_check()
    if not a.query:
        p.error("a search query is required")

    passed, rejected = screen(a.query, a.limit)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"query": a.query, "screened_at": datetime.now(timezone.utc).isoformat(),
         "passed": passed, "rejected": rejected}, indent=2))

    print(f"\n{len(passed)} passed, {len(rejected)} rejected -> {out}")
    for r in passed:
        who = ", ".join(f"{c['name'] or c['login']} <{c['email']}>" for c in r["contacts"])
        print(f"  {r['repo']}  {r['stars']}*  ts={r['ts_share']:.0%}  {who}")


if __name__ == "__main__":
    main()

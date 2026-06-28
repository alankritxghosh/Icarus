# demo/links.py
"""Map a normalized "source:ref" citation to its source URL on GitHub.

Citations are rendered as clickable links so cite-or-unknown is tangible on
screen. An unknown source (or a malformed ref) returns None -- the page shows
the ref as plain text rather than a broken link.
"""


def ref_to_url(ref: str, repo: str, commit: str):
    source, sep, rest = ref.partition(":")
    if not sep or not rest:
        return None
    if source == "pr":
        return f"https://github.com/{repo}/pull/{rest}"
    if source == "issue":
        return f"https://github.com/{repo}/issues/{rest}"
    if source == "code":
        return f"https://github.com/{repo}/blob/{commit}/{rest}"
    return None

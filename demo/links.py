# demo/links.py
"""Map a normalized "source:ref" citation to its source URL on GitHub.

Citations are rendered as clickable links so cite-or-unknown is tangible on
screen. `code:`, `doc:`, and `config:` all resolve to a GitHub blob URL, with
an optional `#Lstart-Lend` fragment appended verbatim when the ref carries a
line range. An unknown source (or a malformed ref) returns None -- the page
shows the ref as plain text rather than a broken link.
"""


def ref_to_url(ref: str, repo: str, commit: str):
    source, sep, rest = ref.partition(":")
    if not sep or not rest:
        return None
    if source == "pr":
        return f"https://github.com/{repo}/pull/{rest}"
    if source == "issue":
        return f"https://github.com/{repo}/issues/{rest}"
    if source == "commit":
        return f"https://github.com/{repo}/commit/{rest}"
    if source == "diff":
        # The pull request's own diff view -- where the hunks Icarus read are
        # shown in full, rather than the conversation tab.
        return f"https://github.com/{repo}/pull/{rest}/files"
    if source in ("code", "doc", "config"):
        path, hash_sep, line_range = rest.partition("#")
        fragment = f"#{line_range}" if hash_sep else ""
        return f"https://github.com/{repo}/blob/{commit}/{path}{fragment}"
    return None

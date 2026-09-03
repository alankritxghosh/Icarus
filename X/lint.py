#!/usr/bin/env python3
"""Check a draft before it ships. Reads stdin or a file.

Hard fails are things the X composer or the voice rules make non-negotiable.
Warnings are the tells that a draft was written by a model rather than by
someone who did the work. Run --selftest first: a checker that has never been
seen to fail proves nothing.
"""
import re, sys

HARD = [
    ("em/en dash", r"[—–]", "Use a full stop. He does not write dashes."),
    ("ellipsis", r"…|\.\.\.", "Finish the sentence or cut it."),
    ("smart quotes", r"[‘’“”]", "Straight quotes only. Smart quotes come from a word processor, not a keyboard."),
    ("emoji", r"[\U0001F300-\U0001FAFF☀-➿]", "Never."),
    ("hashtag", r"(?<!\w)#[A-Za-z]", "Never."),
]

SLOP = ["delve","leverage","robust","seamless","landscape","realm","testament",
        "underscore","pivotal","crucial","unlock","tapestry","myriad","plethora",
        "elevate","empower","streamline","holistic","paradigm","cutting-edge",
        "game-changer","deep dive","supercharge","transformative","comprehensive",
        "meticulous","boasts","navigating","harnessing","in today's","the world of"]

WARN = [
    ("not-just construction", r"(\bnot|n.t) (just|only|merely)\b", "Overused AI cadence. State the thing."),
    ("isn't-X-it's-Y", r"\b(isn't|is not|wasn't)\b[^.]{0,60}\bit'?s\b", "Fine once. It is a tic when every draft has one."),
    ("rhetorical question", r"\?\s*$", "He does not ask the reader questions."),
    ("that's-the closer", r"(?im)^(that'?s|this is) (the|what|why|how)\b", "Aphoristic closer. Delete the last line."),
    ("adverb pile", r"(\b\w+ly\b.*){3,}", "Three -ly adverbs. Cut two."),
    ("triad", r"\b\w+, \w+,? and \w+\b", "Rule of three. Reads as copywriting."),
    ("hedge", r"\b(arguably|essentially|fundamentally|ultimately|simply put)\b", "Cut it."),
    ("bold tic", r"\*\*", "Bold is for the repo files, never for a post or reply."),
]

def check(text, limit=280):
    fails, warns = [], []
    for name, pat, why in HARD:
        for m in re.finditer(pat, text):
            fails.append(f"{name}: {m.group()!r} - {why}")
    low = text.lower()
    for w in SLOP:
        if w in low:
            fails.append(f"slop word: {w!r} - not his vocabulary")
    for name, pat, why in WARN:
        if re.search(pat, text):
            warns.append(f"{name} - {why}")
    n = len(text)
    if n > limit:
        fails.append(f"length: {n} chars, over {limit}")
    if not re.search(r"\d", text):
        warns.append("no number - could have been written without doing the work")
    if re.search(r"\d{1,3},?\d{3}\b", text) is None and re.search(r"\b(many|several|lots of|a bunch of|hundreds|thousands)\b", low):
        fails.append("rounded quantity - use the count or cut the sentence")
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) == 1 and n > 140:
        warns.append("one block - hard line breaks are the voice, and the composer eats them on paste")
    return fails, warns, n

def report(label, text):
    f, w, n = check(text)
    print(f"\n{label}  [{n} chars]")
    for x in f: print("  FAIL ", x)
    for x in w: print("  warn ", x)
    if not f and not w: print("  clean")
    return not f

def selftest():
    bad = "This isn't just a change, it's a fundamentally robust way to delve into the landscape — that's why it matters."
    f, w, _ = check(bad)
    assert any("em/en dash" in x for x in f), "dash check dead"
    assert any("delve" in x for x in f), "slop check dead"
    assert any("not-just" in x for x in w), "cadence check dead"
    good = "I read 60 pull requests on one repo. 11 were closed unmerged. Only 2 had a reviewer asking for changes."
    f2, _, _ = check(good)
    assert not f2, f"false positive: {f2}"
    print("selftest ok")

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif len(sys.argv) > 1:
        report(sys.argv[1], open(sys.argv[1]).read())
    else:
        report("stdin", sys.stdin.read())

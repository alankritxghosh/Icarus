"""Append-only record of what was actually sent, and what actually happened.

    python3 sales/send_log.py send   --person "Maria Diaz" --email m@x.io \
                                     --repo owner/name --campaign 2026-08-batch1 \
                                     --subject "..."
    python3 sales/send_log.py observe --email m@x.io --kind reply --detail "..."
    python3 sales/send_log.py checked --campaign 2026-08-batch1 --source gmail
    python3 sales/send_log.py report  [--campaign ...]
    python3 sales/send_log.py --self-check

WHY THIS EXISTS. Three campaigns, ~104 sends, and the outcome recorded was
"0 replies" -- which cannot be told apart from "0 delivered". No send was
recorded as an event; `site/for/outreach_log.jsonl` is a hand-written diary
whose first row compresses 23 sends into one line and whose largest campaign
(71 sends) is absent entirely. A diary records what someone concluded. This
records what happened.

THE ONE RULE THIS ENFORCES. Delivery is THREE-VALUED and starts at UNKNOWN.
"No bounce seen" is only evidence of delivery if someone actually looked, so
until a `checked` event says the mailbox was reconciled, every send reports
`unknown`, never `delivered`. This is the same discipline `demo/freshness.py`
applies to a stale index: telling you it is fine because the check failed is
the failure being prevented. A funnel that quietly promotes unknown to
delivered would reproduce the exact ambiguity this file exists to remove.

Gmail is the source of truth for bounces and replies -- it already has them.
This does not poll Gmail (a cron job with a mail credential is a bigger thing
than the problem); `observe` and `checked` are how a Gmail read gets written
down, whether done by hand or by an agent with mailbox access.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "outputs" / "leads" / "sends.jsonl"

KINDS = ("bounce", "reply", "unsubscribe")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def send_id(email, campaign):
    """Stable id for one (person, campaign) so observations attach later.

    Keyed on the ADDRESS, not the display name: a name is retyped differently
    every time and would silently create a second identity for one human.
    """
    key = f"{(email or '').strip().lower()}|{(campaign or '').strip()}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def append(row, path=LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read(path=LOG):
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"skipping unparseable line: {line[:80]}", file=sys.stderr)
    return out


def funnel(events, campaign=None):
    """Counts, with unknown as its own bucket rather than folded into good news."""
    if campaign:
        events = [e for e in events if e.get("campaign") == campaign]

    sends, bounced, replied, unsub = {}, set(), set(), set()
    checked = {}          # channel -> latest reconcile timestamp
    for e in events:
        ev, sid = e.get("event"), e.get("id")
        if ev == "send":
            sends[sid] = e
        elif ev == "bounce":
            bounced.add(sid)
        elif ev == "reply":
            replied.add(sid)
        elif ev == "unsubscribe":
            unsub.add(sid)
        elif ev == "checked":
            ch, at = e.get("channel", "email"), e.get("at")
            checked[ch] = max(checked[ch], at) if checked.get(ch) else at

    # Only ids that were actually sent can be counted against the funnel.
    bounced &= sends.keys()
    replied &= sends.keys()
    unsub &= sends.keys()

    # THE distinction the last three campaigns could not make -- and it is
    # PER CHANNEL. Reconciling Gmail says nothing about a message sent as an
    # X DM: that is exactly how Richie McIlroy's "very interesting!" stayed
    # invisible while the campaign was written up as "0 positive replies".
    delivered = unknown = 0
    for sid, s in sends.items():
        if checked.get(s.get("channel", "email")):
            delivered += 0 if sid in bounced else 1
        else:
            unknown += 1

    return {
        "campaign": campaign or "(all)",
        "sent": len(sends),
        "people": len({s.get("email", "").lower() for s in sends.values()}),
        "channels": dict(Counter(s.get("channel", "email") for s in sends.values())),
        "bounced": len(bounced),
        "replied": len(replied),
        "unsubscribed": len(unsub),
        "delivered": delivered,
        "delivery_unknown": unknown,
        "checked": checked,
        "unchecked_channels": sorted(
            {s.get("channel", "email") for s in sends.values()} - set(checked)),
        "reply_rate": round(len(replied) / delivered, 4) if delivered else None,
    }


def render(f):
    chans = ", ".join(f"{k}:{v}" for k, v in sorted(f["channels"].items())) or "-"
    lines = [f"campaign         {f['campaign']}",
             f"sent             {f['sent']}  ({f['people']} distinct addresses)",
             f"channels         {chans}",
             f"bounced          {f['bounced']}",
             f"replied          {f['replied']}",
             f"unsubscribed     {f['unsubscribed']}",
             f"delivered        {f['delivered']}"
             + ("" if not f["delivery_unknown"]
                else f"   ({f['delivery_unknown']} of {f['sent']} UNKNOWN)"),
             "reply rate       " + (f"{f['reply_rate']:.1%} of delivered"
                                    if f["reply_rate"] is not None
                                    else "n/a -- nothing confirmed delivered")]
    for ch, at in sorted(f["checked"].items()):
        lines.append(f"reconciled       {ch} @ {at}")
    if f["unchecked_channels"]:
        lines += ["",
                  "  NEVER RECONCILED: " + ", ".join(f["unchecked_channels"]),
                  "  Those sends count as delivery UNKNOWN, not delivered. A zero",
                  "  reply count on an unreconciled channel means nothing -- it is",
                  "  indistinguishable from nothing having arrived. Run:",
                  "    python3 sales/send_log.py checked --campaign <name> "
                  "--channel <channel>",
                  "  Reconciling one channel says NOTHING about another: a Gmail",
                  "  sync cannot see an X DM, which is how one positive reply went",
                  "  unrecorded while the batch was written up as a total failure."]
    return "\n".join(lines)


def self_check():
    ev = []

    def snd(email, campaign="c1", channel="email"):
        row = {"at": now_iso(), "event": "send", "id": send_id(email, campaign),
               "email": email, "campaign": campaign, "channel": channel}
        ev.append(row)
        return row["id"]

    a, b = snd("a@x.io"), snd("b@x.io")

    # THE property: before any reconciliation, delivery is unknown -- not zero,
    # not "fine". Revert this to `delivered = sent - bounced` and it fails.
    f = funnel(ev)
    assert f["sent"] == 2 and f["delivered"] == 0 and f["delivery_unknown"] == 2, f
    assert f["reply_rate"] is None
    assert "UNKNOWN" in render(f)

    # a bounce is knowledge even before a full reconcile, but does not grant it
    ev.append({"at": now_iso(), "event": "bounce", "id": a, "campaign": "c1"})
    assert funnel(ev)["bounced"] == 1
    assert funnel(ev)["delivery_unknown"] == 2, "one bounce is not a reconcile"

    # after reconciling, and only then, delivery becomes a number
    ev.append({"at": now_iso(), "event": "checked", "campaign": "c1",
               "source": "gmail", "channel": "email"})
    f = funnel(ev)
    assert f["delivered"] == 1 and f["delivery_unknown"] == 0, f
    assert f["reply_rate"] == 0.0, "reconciled and no replies IS a real zero"

    ev.append({"at": now_iso(), "event": "reply", "id": b, "campaign": "c1"})
    assert funnel(ev)["reply_rate"] == 1.0

    # the same human in two campaigns is two sends; in one campaign, one id
    assert send_id("a@x.io", "c1") == send_id("A@X.io ", "c1"), "address is the key"
    assert send_id("a@x.io", "c1") != send_id("a@x.io", "c2")

    # an observation for someone never sent to cannot inflate the funnel
    ev.append({"at": now_iso(), "event": "reply", "id": "deadbeef", "campaign": "c1"})
    assert funnel(ev)["replied"] == 1, "a reply with no matching send is ignored"

    # campaign filter isolates
    snd("c@x.io", "c2")
    assert funnel(ev, "c2")["sent"] == 1
    assert funnel(ev, "c2")["delivery_unknown"] == 1, "c1's reconcile is not c2's"

    # THE Richie case: reconciling Gmail must not vouch for an X DM.
    dm = snd("x:richiemcilroy", "c1", channel="x_dm")
    f = funnel(ev, "c1")
    assert f["delivery_unknown"] == 1, f       # the DM, and only the DM
    assert f["unchecked_channels"] == ["x_dm"], f
    assert "NEVER RECONCILED: x_dm" in render(f)
    # a reply on that channel is still counted -- it is observed, not inferred
    ev.append({"at": now_iso(), "event": "reply", "id": dm, "campaign": "c1",
               "channel": "x_dm", "detail": "very interesting!"})
    assert funnel(ev, "c1")["replied"] == 2
    # ...and reconciling the DM channel resolves it
    ev.append({"at": now_iso(), "event": "checked", "campaign": "c1",
               "channel": "x_dm", "source": "x"})
    assert funnel(ev, "c1")["delivery_unknown"] == 0

    assert read(Path("/nonexistent/sends.jsonl")) == []
    print("self-check ok")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-check", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("send", help="record one message actually sent")
    s.add_argument("--person"); s.add_argument("--email", required=True)
    s.add_argument("--repo"); s.add_argument("--campaign", required=True)
    s.add_argument("--subject"); s.add_argument("--link")
    s.add_argument("--channel", default="email")

    o = sub.add_parser("observe", help="record a bounce / reply / unsubscribe")
    o.add_argument("--email", required=True); o.add_argument("--campaign", required=True)
    o.add_argument("--kind", required=True, choices=KINDS)
    o.add_argument("--detail"); o.add_argument("--at")
    o.add_argument("--channel", default="email")

    c = sub.add_parser("checked", help="record that a CHANNEL was reconciled")
    c.add_argument("--campaign", required=True)
    c.add_argument("--source", default="gmail")
    c.add_argument("--channel", default="email")

    r = sub.add_parser("report", help="the funnel")
    r.add_argument("--campaign")

    a = p.parse_args()
    if a.self_check:
        return self_check()
    if not a.cmd:
        return p.print_help()

    if a.cmd == "send":
        row = append({"at": now_iso(), "event": "send",
                      "id": send_id(a.email, a.campaign), "person": a.person,
                      "email": a.email, "repo": a.repo, "campaign": a.campaign,
                      "subject": a.subject, "link": a.link, "channel": a.channel})
        print(f"logged send {row['id']} -> {a.email} via {a.channel}")
    elif a.cmd == "observe":
        row = append({"at": a.at or now_iso(), "event": a.kind,
                      "id": send_id(a.email, a.campaign), "email": a.email,
                      "campaign": a.campaign, "detail": a.detail,
                      "channel": a.channel})
        print(f"logged {a.kind} {row['id']} <- {a.email} via {a.channel}")
    elif a.cmd == "checked":
        append({"at": now_iso(), "event": "checked", "campaign": a.campaign,
                "source": a.source, "channel": a.channel})
        print(f"reconciled {a.campaign} on {a.channel} against {a.source}")
    elif a.cmd == "report":
        print(render(funnel(read(), a.campaign)))


if __name__ == "__main__":
    main()

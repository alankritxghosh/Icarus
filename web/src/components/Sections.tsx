"use client";

import { Reveal } from "./Reveal";
import { Section } from "./Section";

import release from "@/generated/release.json";

// Every release fact on this page comes from release.json, which
// scripts/check_release.py proves against the real binary. It used to be a
// hardcoded sha and a hardcoded "~2352 KB", which meant a new release needed
// the page edited by hand and nothing noticed when it wasn't.
const DMG_SHA: string = release.dmg.sha256;
const DMG_KB = Math.round(release.dmg.bytes / 1024);
const VERSION: string = release.version;

/* ---------------------------------------------------------------------------
   Every claim below is copied from the shipped site, which was itself checked
   against the code. Nothing here is new marketing: the refusal wording, the
   limits, the install steps and the checksum are the approved ones.
   --------------------------------------------------------------------------- */

export function Refusal() {
  return (
    <Section
      id="refusal"
      art="/art/icarus-fall.jpg"
      eyebrow="The part nobody else demos"
      title="It tells you when it doesn't know."
      lede="Other assistants guess, confidently, and never say it was a guess. Icarus refuses instead, and the refusal is enforced by code rather than by asking a model nicely."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Reveal>
          <article className="glass h-full p-5">
            <p className="font-mono text-[11px] uppercase tracking-wider text-cited">
              A reason that was recorded
            </p>
            <p className="mt-3 text-[15px] leading-relaxed">
              The answer arrives with the pull requests and issues it rests on. Every citation
              resolves to evidence that was really retrieved, with a valid line range.
            </p>
            {/*
              No sample citations here on purpose. The first draft showed
              issue:6856, issue:6752 and pr:1442 side by side -- two from
              psf/requests and one from simonw/llm -- which implies a single
              answer cited all three. It never did. Decorative evidence is the
              exact thing this product exists to refuse, so the real citations
              in the hero are the only ones on the page.
            */}
            <p className="mt-4 font-mono text-[11px] text-muted">
              Ask something above to see real ones.
            </p>
          </article>
        </Reveal>
        <Reveal delay={0.08}>
          <article className="glass h-full p-5">
            <p className="font-mono text-[11px] uppercase tracking-wider text-unknown">
              A reason nobody recorded
            </p>
            <p className="mt-3 text-[15px] leading-relaxed">
              &ldquo;No one wrote this down.&rdquo; Icarus found the code and found no recorded
              reason, so it will not invent one. This is the refusal working, not a failure.
            </p>
            <p className="mt-4 font-mono text-[11px] text-muted">
              It will abstain more often than you expect. That is the design.
            </p>
          </article>
        </Reveal>
      </div>
    </Section>
  );
}

const STEPS = [
  { n: "01", h: "Connect a repository",
    p: "Sign in with GitHub, point Icarus at a repo. It indexes source, pull requests and issues — 22 file types, ~17 languages." },
  { n: "02", h: "Hold a key and ask",
    p: "Hold Right Option anywhere on your Mac and speak, or press ⌘⇧I to type." },
  { n: "03", h: "Read the proof",
    p: "A one-line spoken answer, with the quoted evidence on screen linked to the exact lines on GitHub. Or nobody recorded a reason, and it says so." },
];

export function HowItWorks() {
  return (
    <Section id="how" art="/art/icarus-wings.jpg" eyebrow="How it works" title="Three steps, then it is just there.">
      <div className="grid gap-4 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <Reveal key={s.n} delay={i * 0.07}>
            <article className="glass h-full p-5">
              <p className="font-mono text-xs text-signal">{s.n}</p>
              <h3 className="mt-3 font-semibold">{s.h}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{s.p}</p>
            </article>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

const LIMITS = [
  ["It does not write code for you.", "This is not a coding agent."],
  ["It cannot cite evidence it did not retrieve.",
   "Every citation must resolve to real retrieved evidence with a valid line range, or the answer is refused."],
  ["It will abstain more than you expect.",
   "If nobody wrote down why, it says so rather than reconstruct a plausible story."],
  ["It is an alpha.", "Large repositories index slowly, and it is not notarized yet."],
];

export function Limits() {
  return (
    <Section
      art="/art/icarus-sea.jpg"
      eyebrow="What it will not do"
      title="A tool that hides its limits is asking to be trusted rather than checked."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {LIMITS.map(([h, p], i) => (
          <Reveal key={h} delay={i * 0.05}>
            <div className="glass h-full p-5">
              <h3 className="text-[15px] font-semibold">{h}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{p}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

export function ForAgents() {
  return (
    <Section
      id="agents"
      eyebrow="What your agent cannot see"
      title="Claude Code, Cursor, Codex"
      lede="A merged pull request leaves a commit. A refused one leaves nothing, so git log, git blame and the working tree are blind to every change your team tried and closed. Your agent reads exactly those three. Icarus reads the rest."
    >
      <Reveal>
        <pre className="glass overflow-x-auto p-5 font-mono text-[12px] leading-relaxed text-muted">
{`{
  "mcpServers": {
    "icarus": {
      "type": "stdio",
      "command": "/Applications/Icarus.app/Contents/MacOS/Icarus",
      "args": ["--mcp"]
    }
  }
}`}
        </pre>
      </Reveal>
      <Reveal delay={0.08}>
        <p className="mt-4 text-sm leading-relaxed text-muted">
          The app is the server — no package, no credential to paste. For Claude Code this is
          already done if you followed Get started; Settings shows live status and can repair it.
        </p>
      </Reveal>
    </Section>
  );
}

const INSTALL = [
  ["01", "Install", "Download the .dmg, or use the terminal path below."],
  ["02", "Sign in", "Open Icarus, click “Sign in with GitHub.” Asks for your identity only — nothing else, yet."],
  ["03", "Connect a repo", "Type owner/repo and press Connect. Icarus indexes it — seconds to a few minutes."],
  ["04", "Claude Code — one time", "Settings → Connect, approve Keychain access. Skip if you don’t use Claude Code."],
];

export function Install() {
  return (
    <Section
      id="install"
      art="/art/icarus-flight.jpg"
      eyebrow="Install"
      title="Four steps, about two minutes."
      lede="Not notarized — that needs a paid Developer ID this alpha does not have — so the checksum is below and you can verify the download yourself."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {INSTALL.map(([n, h, p], i) => (
          <Reveal key={n} delay={i * 0.06}>
            <article className="glass h-full p-5">
              <p className="font-mono text-xs text-signal">{n}</p>
              <h3 className="mt-3 text-[15px] font-semibold">{h}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{p}</p>
            </article>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.08}>
        <div className="glass mt-8 flex flex-wrap items-center gap-x-5 gap-y-3 p-5">
          <a
            href="/Icarus.dmg"
            className="flex items-center gap-2 rounded-full bg-sun px-5 py-3 text-[14px] font-semibold text-deep transition hover:brightness-110"
          >
            ↓ Download for macOS
          </a>
          <div className="font-mono text-[11px] leading-relaxed text-muted">
            Apple silicon · v{VERSION} · ~{DMG_KB.toLocaleString()} KB · free alpha
            <span className="mt-1 block">
              Not notarized yet, so the first launch takes one extra click:
              right-click the app → Open.
            </span>
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.12}>
        <div className="glass mt-4 p-5">
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted">
            Terminal — recommended
          </p>
          <pre className="mt-3 overflow-x-auto font-mono text-[12px] leading-relaxed">
{`curl -fsSLO https://icarus-website-kappa.vercel.app/install.sh
less install.sh   # ~100 lines, half of them comments — read it
sh install.sh`}
          </pre>
          <p className="mt-4 break-all font-mono text-[11px] text-muted">
            SHA-256 · {DMG_SHA}
          </p>
        </div>
      </Reveal>
    </Section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-hair px-6 py-10">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-[11px] text-muted">Icarus · macOS · alpha</p>
        <p className="font-mono text-[11px] text-muted">
          Your code is never used to train any model, and is discarded after each request.
        </p>
      </div>
    </footer>
  );
}

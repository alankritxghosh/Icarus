"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { BorderTrail } from "./BorderTrail";
import type { Cite } from "./EvidenceGraph";

type Verdict = "answer" | "unknown" | "error";
type Result = { verdict: Verdict; label: string; text: string; cites: Cite[] };

const EXAMPLES = [
  "Why was hide_reasoning added when -R already existed?",
  "What concrete use case drove the PauseChain primitive in llm?",
  "Why is the maximum conversation-name length set to 32 characters?",
];

export default function TryBox({
  onEvidence,
}: {
  onEvidence: (cited: Cite[] | null, searched: Cite[] | null) => void;
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Result | null>(null);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setBusy(true);
    setRes(null);
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const b = await r.json();
      onEvidence(b.citations ?? null, b.searched ?? null);
      if (r.status === 429) {
        setRes({ verdict: "error", label: "at capacity",
          text: "The public demo is capped by the hour, on purpose: every answer costs money.", cites: [] });
      } else if (!r.ok) {
        setRes({ verdict: "error", label: "unavailable",
          text: b.error || "The brain did not answer. Try again shortly.", cites: [] });
      } else if (b.verdict === "answer") {
        setRes({ verdict: "answer", label: "answered, with citations", text: b.answer, cites: b.citations || [] });
      } else {
        setRes({ verdict: "unknown", label: "no one wrote this down",
          text: "Icarus found the code but no recorded reason, so it will not invent one. This is the refusal working, not a failure.",
          cites: b.citations || [] });
      }
    } catch {
      setRes({ verdict: "error", label: "unavailable", text: "Could not reach the brain from this browser.", cites: [] });
    } finally {
      setBusy(false);
    }
  }

  const tone =
    res?.verdict === "answer" ? "text-cited"
    : res?.verdict === "unknown" ? "text-unknown"
    : "text-muted";

  return (
    <div className="w-full max-w-2xl">
      <div className="glass relative flex items-center gap-2 p-2">
        {busy && <BorderTrail size={56} />}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(q)}
          placeholder="Why was hide_reasoning added when -R already existed?"
          spellCheck={false}
          className="min-w-0 flex-1 bg-transparent px-3 py-3 text-[15px] outline-none placeholder:text-muted/70"
        />
        <button
          onClick={() => ask(q)}
          disabled={busy}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-ink px-4 py-3 text-sm font-medium text-paper transition hover:opacity-90 disabled:opacity-60"
        >
          {busy ? "Reading" : "Ask"}
          {!busy && <ArrowRight className="size-4" />}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((e) => (
          <button
            key={e}
            onClick={() => { setQ(e); ask(e); }}
            className="glass glass-sm !rounded-full px-3 py-1.5 text-left text-xs text-muted transition hover:text-ink"
          >
            {e}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {res && (
          <motion.div
            key={res.label + res.text.slice(0, 24)}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="glass mt-4 p-4"
          >
            <div className={`font-mono text-[11px] uppercase tracking-wider ${tone}`}>{res.label}</div>
            <p className="mt-2 text-[15px] leading-relaxed">{res.text}</p>
            {res.cites.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {res.cites.map((c, i) => {
                  const ref = typeof c === "string" ? c : c.ref;
                  const url = typeof c === "string" ? undefined : (c as { url?: string }).url;
                  return (
                    <motion.a
                      key={ref! + i}
                      initial={{ opacity: 0, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.04 * i, duration: 0.2 }}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-md border border-hair px-2 py-1 font-mono text-[11px] text-muted transition hover:border-cited hover:text-cited"
                    >
                      {ref}
                    </motion.a>
                  );
                })}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

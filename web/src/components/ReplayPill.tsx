"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

/**
 * The replay. Ported from the shipped site, where it is the only thing on the
 * page that shows the product working rather than describing it: a real
 * recorded exchange, then a real refusal.
 *
 * Both scenes are verbatim from site/index.html. They are a REPLAY and the
 * caption says so -- this is not a live call dressed up as one.
 */
type Scene = {
  q: string; a: string; refuse: boolean;
  excerpt?: string; refs: string[]; note?: string;
};

const SCENES: Scene[] = [
  {
    q: "Why does requests not support HTTP/2?",
    refuse: false,
    a:
      "HTTP/2 is a complex protocol, and it is unlikely that Requests will achieve good " +
      "support for it in its current form anytime soon. Additionally, support is likely " +
      "blocked by the lack of HTTP/2 support in the underlying urllib3 library.",
    excerpt:
      "Issue #6856: HTTP/2\nI am trying to get HTTP/2 with requests, and I found these:\n> It can: http://hyper.readthedocs.org/en/development/…\n…",
    refs: ["issue:6856", "issue:6752"],
  },
  {
    q: "Why is the redirect limit 30?",
    refuse: true,
    a: "No one wrote this down.",
    refs: [],
    note: "searched 20 sources · 0 recorded reasons",
  },
];

type Phase = "typing" | "listening" | "answer";

export default function ReplayPill() {
  const [i, setI] = useState(0);
  const [phase, setPhase] = useState<Phase>("typing");
  const [typed, setTyped] = useState("");
  const wave = useRef<HTMLCanvasElement>(null);
  const scene = SCENES[i];

  // type -> listen -> answer -> hold -> next scene
  useEffect(() => {
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const at = (ms: number, fn: () => void) => timers.push(setTimeout(fn, ms));

    const q = scene.q;
    for (let c = 0; c <= q.length; c++) {
      at(28 * c, () => !cancelled && setTyped(q.slice(0, c)));
    }
    const typeMs = 28 * q.length;
    at(typeMs + 220, () => setPhase("listening"));
    at(typeMs + 1250, () => setPhase("answer"));
    at(typeMs + 1250 + (scene.refuse ? 4200 : 6400), () => {
      if (cancelled) return;
      setTyped("");
      setPhase("typing");
      setI((n) => (n + 1) % SCENES.length);
    });

    return () => { cancelled = true; timers.forEach(clearTimeout); };
  }, [i, scene.q, scene.refuse]);

  // The waveform. Only moves while it is listening, because a waveform that
  // moves when nothing is happening is a lie told in pixels.
  useEffect(() => {
    const cv = wave.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    let raf = 0, t = 0;
    const draw = () => {
      const w = cv.width, h = cv.height;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = phase === "listening" ? "#ffc76b" : "#4a4459";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let x = 0; x < w; x += 3) {
        const amp = phase === "listening"
          ? Math.sin(x * 0.09 + t) * Math.sin(x * 0.021 + t * 0.7) * (h / 2 - 2)
          : Math.sin(x * 0.09) * 0.6;
        ctx.moveTo(x, h / 2 - amp);
        ctx.lineTo(x, h / 2 + amp);
      }
      ctx.stroke();
      t += 0.16;
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [phase]);

  return (
    <div className="glass glass-lg w-full max-w-[470px] p-4">
      <div className="flex min-h-[22px] items-center gap-2.5">
        <span
          className={`size-2 rounded-full transition-colors ${
            phase === "listening" ? "bg-sun" : "bg-hair"
          }`}
        />
        <canvas ref={wave} width={150} height={18} className="h-[18px] w-[150px]" aria-hidden />
        <span className="truncate font-mono text-[11px] text-muted">
          {typed}
          {phase === "typing" && <i className="caret" />}
        </span>
      </div>

      <AnimatePresence mode="wait">
        {phase === "answer" && (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
            className="mt-3 border-t border-hair pt-3"
          >
            {scene.refuse ? (
              <p className="font-mono text-[20px] font-bold leading-snug text-unknown">
                {scene.a}
              </p>
            ) : (
              <p className="text-[15px] leading-relaxed">{scene.a}</p>
            )}

            {scene.excerpt && (
              <motion.pre
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}
                className="mt-3 whitespace-pre-wrap rounded-lg border border-white/10 bg-deep/50 p-3 font-mono text-[11px] leading-relaxed text-muted"
              >
                {scene.excerpt}
              </motion.pre>
            )}

            <div className="mt-3 flex flex-wrap gap-1.5">
              {scene.refs.map((r, n) => (
                <motion.span
                  key={r}
                  initial={{ opacity: 0, scale: 0.94 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.5 + n * 0.14 }}
                  className="rounded-md border border-cited/40 px-2 py-1 font-mono text-[11px] text-cited"
                >
                  {r}
                </motion.span>
              ))}
            </div>

            {scene.note && (
              <motion.p
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.45 }}
                className="mt-3 font-mono text-[11px] text-muted"
              >
                {scene.note}
              </motion.p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <p className="mt-3 font-mono text-[10px] text-muted/70">
        Replaying a real exchange · psf/requests
      </p>
    </div>
  );
}

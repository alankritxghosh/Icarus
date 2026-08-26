"use client";

import { useEffect, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { Download, Home, ShieldAlert, Terminal, Workflow, Bot } from "lucide-react";
import release from "@/generated/release.json";

/** The wings. Same geometry as the Mac app's mark and the favicon. */
export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden fill="currentColor">
      <g>
        <path
          id="wing"
          d="M49 54 Q65.73 51.58 80.98 55.12 Q65.6 55.48 49 54 Z
             M49 54 Q67.95 48.76 86.05 50.63 Q68.36 53.29 49 54 Z
             M49 54 Q69.67 45.36 90.41 44.9 Q70.79 50.44 49 54 Z
             M49 54 Q70.81 41.46 93.84 38.03 Q72.77 46.97 49 54 Z
             M49 54 Q71.25 37.16 96.13 30.19 Q74.18 42.96 49 54 Z
             M49 54 Q70.93 32.58 97.08 21.57 Q74.93 38.5 49 54 Z
             M49 54 L97.08 21.57 Q81.83 39.32 80.77 45.96 Z"
        />
        <use href="#wing" transform="translate(100,0) scale(-1,1)" />
        <path d="M42 46 L49.3 46 L49.3 72 Z M58 46 L50.7 46 L50.7 72 Z" />
      </g>
    </svg>
  );
}

/** Scroll progress, carried over from the shipped site. */
export function FallLine() {
  useEffect(() => {
    const el = document.querySelector<HTMLElement>(".fallline");
    if (!el) return;
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      el.style.setProperty("--scroll", String(max > 0 ? window.scrollY / max : 0));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return <div className="fallline" aria-hidden />;
}

/**
 * The header. The download stays in the top right at every scroll position,
 * because a CTA you have to hunt for is a CTA that gets skipped.
 */
export function Header() {
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        solid ? "border-b border-white/10 bg-deep/70 backdrop-blur-xl saturate-150" : "border-b border-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
        <a href="#top" className="flex items-center gap-2.5">
          <Mark className="size-7 text-sun" />
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
            Icarus
          </span>
        </a>
        <div className="flex items-center gap-3">
          <span className="hidden font-mono text-[11px] text-muted sm:inline">
            free alpha · Apple silicon
          </span>
          {/* A real download, not a jump to a section that then tells you to
              download. The CTA was an #install anchor and the install section
              had no .dmg link at all, so the whole path dead-ended. */}
          <a
            href={release.url}
            className="group flex items-center gap-2 rounded-full bg-sun px-4 py-2 text-[13px] font-semibold text-deep transition hover:brightness-110"
          >
            <Download className="size-4" />
            Download
          </a>
        </div>
      </div>
    </header>
  );
}

const DOCK = [
  { id: "top", label: "Top", Icon: Home },
  { id: "refusal", label: "The refusal", Icon: ShieldAlert },
  { id: "how", label: "How it works", Icon: Workflow },
  { id: "agents", label: "For agents", Icon: Bot },
  { id: "install", label: "Install", Icon: Terminal },
];

/**
 * A dock, in the spirit of motion-primitives' Dock: icons magnify with the
 * cursor's distance along the bar. Rewritten rather than installed, for the
 * same reason as the other borrowings -- that library is a React+Tailwind
 * package and this is the only part of it the page uses.
 */
export function Dock() {
  const mouseX = useMotionValue(Infinity);
  return (
    <nav
      onMouseMove={(e) => mouseX.set(e.clientX)}
      onMouseLeave={() => mouseX.set(Infinity)}
      className="glass glass-lg fixed bottom-5 left-1/2 z-50 flex -translate-x-1/2 items-end gap-2 px-3 pb-2 pt-2"
    >
      {DOCK.map((d) => (
        <DockItem key={d.id} mouseX={mouseX} {...d} />
      ))}
    </nav>
  );
}

function DockItem({
  mouseX, id, label, Icon,
}: {
  mouseX: ReturnType<typeof useMotionValue<number>>;
  id: string; label: string; Icon: typeof Home;
}) {
  const [el, setEl] = useState<HTMLAnchorElement | null>(null);
  const distance = useTransform(mouseX, (v) => {
    const b = el?.getBoundingClientRect();
    if (!b) return Infinity;
    return v - (b.x + b.width / 2);
  });
  const sizeRaw = useTransform(distance, [-130, 0, 130], [40, 62, 40]);
  const size = useSpring(sizeRaw, { stiffness: 320, damping: 22, mass: 0.4 });

  return (
    <motion.a
      ref={setEl}
      href={`#${id}`}
      style={{ width: size, height: size }}
      className="group relative flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-muted transition-colors hover:text-sun"
      aria-label={label}
    >
      <Icon className="size-[45%]" />
      <span className="pointer-events-none absolute -top-9 whitespace-nowrap rounded-md border border-hair bg-deep px-2 py-1 font-mono text-[10px] opacity-0 transition-opacity group-hover:opacity-100">
        {label}
      </span>
    </motion.a>
  );
}

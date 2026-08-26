import type { ReactNode } from "react";
import { Reveal } from "./Reveal";
import PaintingRelief from "./PaintingRelief";

export function Section({
  eyebrow,
  title,
  lede,
  children,
  id,
  art,
}: {
  eyebrow: string;
  title: string;
  lede?: string;
  children: ReactNode;
  id?: string;
  /** A painting, rendered as displaced relief rather than as a background. */
  art?: string;
}) {
  return (
    <section
      id={id}
      className="relative isolate overflow-hidden border-t border-hair px-6 py-20 md:py-28"
    >
      {art && (
        <>
          <PaintingRelief src={art} className="absolute inset-0 -z-20 h-full w-full" />
          {/* The relief is the texture; this keeps the words on top of it
              readable without flattening it back into wallpaper. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10"
            style={{
              background:
                "linear-gradient(90deg, var(--color-paper) 0%, color-mix(in srgb, var(--color-paper) 88%, transparent) 46%, transparent 88%)",
            }}
          />
        </>
      )}
      <div className="relative mx-auto w-full max-w-5xl">
        <Reveal>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-sun/80">{eyebrow}</p>
          <h2 className="mt-3 text-[clamp(1.6rem,3vw,2.4rem)] font-semibold tracking-tight">
            {title}
          </h2>
          {lede && <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted">{lede}</p>}
        </Reveal>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

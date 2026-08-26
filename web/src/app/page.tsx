"use client";

import { useState } from "react";
import { motion } from "motion/react";
import EvidenceGraph, { type Cite } from "@/components/EvidenceGraph";
import ReplayPill from "@/components/ReplayPill";
import { Dock, FallLine, Header } from "@/components/Chrome";
import TryBox from "@/components/TryBox";
import {
  ForAgents,
  Footer,
  HowItWorks,
  Install,
  Limits,
  Refusal,
} from "@/components/Sections";

const rise = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: 0.06 * i, duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
  }),
};

export default function Home() {
  const [cited, setCited] = useState<Cite[] | null>(null);
  const [searched, setSearched] = useState<Cite[] | null>(null);

  return (
    <main id="top" className="relative pb-28">
      <FallLine />
      <Header />
      <Dock />
      {/* ---- hero: the product first, not an essay about it ---------------- */}
      <section className="relative isolate flex min-h-[100svh] flex-col justify-center overflow-hidden px-6 pb-16 pt-28">
        <EvidenceGraph
          cited={cited}
          searched={searched}
          className="absolute inset-0 -z-10 h-full w-full"
        />
        {/*
          Legibility, without erasing the graph.

          A flat left-to-right gradient dimmed the whole width, so the copy was
          readable and the graph was gone. This is two shaped layers instead:
          an ellipse anchored over the text column that falls off before it
          reaches the open half, and a short fade at the bottom edge so the
          section ends rather than being cut.
        */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              // 115% wide put the transparent stop past the right edge, so the wash
              // was opaque across the whole viewport and the graph was invisible.
              // Sized to the copy column instead: solid to ~45%, gone by ~72%.
              "radial-gradient(58% 78% at 19% 50%, var(--color-paper) 0%, var(--color-paper) 42%, color-mix(in srgb, var(--color-paper) 78%, transparent) 68%, transparent 100%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-32"
          style={{ background: "linear-gradient(to bottom, transparent, var(--color-paper))" }}
        />
        {/* The sun. There is a light source on the page now, and everything
            warm in the palette comes from it. */}
        <div
          aria-hidden
          className="pointer-events-none absolute -z-20 right-[6%] top-[12%] size-[46vw] max-w-[620px] rounded-full opacity-[0.55] blur-[70px]"
          style={{
            background:
              "radial-gradient(circle, rgba(255,199,107,.55) 0%, rgba(240,167,107,.22) 42%, transparent 70%)",
          }}
        />

        <div className="mx-auto w-full max-w-5xl">
          <motion.p
            custom={0} variants={rise} initial="hidden" animate="show"
            className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted"
          >
            Icarus · macOS · alpha
          </motion.p>

          <motion.h1
            custom={1} variants={rise} initial="hidden" animate="show"
            className="mt-5 max-w-3xl text-[clamp(2.4rem,5.6vw,4.2rem)] font-semibold leading-[1.02] tracking-tight"
          >
            Why is the code like this?
            <span className="block text-muted">Ask. Get the receipts.</span>
          </motion.h1>

          <motion.p
            custom={2} variants={rise} initial="hidden" animate="show"
            className="mt-6 max-w-xl text-lg leading-relaxed text-muted"
          >
            Icarus answers from your repository&apos;s own pull requests and issues, shows
            the evidence, and says <span className="text-ink">&ldquo;no one wrote this down&rdquo;</span>{" "}
            when nobody did.
          </motion.p>

          <motion.div custom={3} variants={rise} initial="hidden" animate="show" className="mt-9">
            <TryBox onEvidence={(c, s) => { setCited(c); setSearched(s); }} />
          </motion.div>

          <motion.div
            custom={4} variants={rise} initial="hidden" animate="show"
            className="mt-8"
          >
            <ReplayPill />
          </motion.div>

          <motion.p
            custom={5} variants={rise} initial="hidden" animate="show"
            className="mt-6 font-mono text-[11px] leading-relaxed text-muted/80"
          >
            Live, on <span className="text-ink">simonw/llm</span> · 526 pull requests · 964 issues ·
            1,091 commits · 470 code windows · no sign-in
            <span className="mt-1 block">
              Behind you: the real evidence graph, 2,599 nodes and 934 edges.
              <span className="text-cited"> Green</span> is cited,
              <span className="text-unknown"> amber</span> is searched.
            </span>
          </motion.p>
        </div>
      </section>

      <Refusal />
      <HowItWorks />
      <Limits />
      <ForAgents />
      <Install />
      <Footer />
    </main>
  );
}

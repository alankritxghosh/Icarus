"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

/**
 * Reveal on scroll. In the spirit of motion-primitives' In View, written here
 * because it is four lines and the library is a React+Tailwind package we do
 * not otherwise need.
 *
 * `once` is deliberate: content that re-animates every time it re-enters the
 * viewport is a page that will not sit still while you read it.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

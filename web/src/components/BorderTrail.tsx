"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * A light that travels the border of its parent. Borrowed in spirit from
 * motion-primitives' Border Trail, rewritten because that library is a
 * React+Tailwind package and this is the only piece of it we want.
 *
 * It is used for ONE thing: a question that is genuinely in flight. Motion
 * that means work is happening is honest; motion that means nothing is the
 * decoration this project keeps refusing.
 */
export function BorderTrail({
  className,
  size = 64,
  duration = 3.2,
}: {
  className?: string;
  size?: number;
  duration?: number;
}) {
  return (
    <div className="pointer-events-none absolute inset-0 rounded-[inherit] border border-transparent [mask-clip:padding-box,border-box] [mask-composite:intersect] [mask-image:linear-gradient(transparent,transparent),linear-gradient(#000,#000)]">
      <motion.div
        className={cn("absolute aspect-square bg-cited", className)}
        style={{
          width: size,
          offsetPath: `rect(0auto auto 0 round ${size}px)`,
        }}
        animate={{ offsetDistance: ["0%", "100%"] }}
        transition={{ duration, ease: "linear", repeat: Infinity }}
      />
    </div>
  );
}

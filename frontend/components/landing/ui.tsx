import { motion } from "motion/react";
import type { ReactNode } from "react";

export const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];

export function Label({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-widest text-ink">
      <span className="h-2 w-2 rounded-full bg-orange" />[ {children} ]
    </span>
  );
}

export function Btn({
  children,
  variant = "orange",
  href = "#",
}: {
  children: ReactNode;
  variant?: "orange" | "paper";
  href?: string;
}) {
  const v =
    variant === "orange" ? "bg-orange hover:bg-orange-hover text-ink" : "bg-paper text-ink";
  return (
    <a
      href={href}
      className={`brut-btn inline-flex items-center gap-2 px-6 py-3.5 text-base font-bold ${v}`}
    >
      {children}
    </a>
  );
}

export function FadeUp({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 32 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

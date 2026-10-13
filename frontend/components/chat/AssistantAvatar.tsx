"use client";

import Image from "next/image";
import { motion, useReducedMotion } from "framer-motion";

export function AssistantAvatar({ thinking = false }: { thinking?: boolean }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      aria-label={thinking ? "MindMesh is thinking" : "MindMesh assistant"}
      className="relative mt-1 grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-[10px] border-2 border-ink bg-[#111]"
      animate={thinking && !reduceMotion ? {
        scale: [1, 1.06, 1],
        rotate: [0, -3, 3, 0],
        boxShadow: ["0 0 0 0 rgba(255,92,0,0)", "0 0 14px 2px rgba(255,92,0,.48)", "0 0 0 0 rgba(255,92,0,0)"],
      } : { scale: 1, rotate: 0, boxShadow: "0 0 0 0 rgba(255,92,0,0)" }}
      transition={thinking ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
    >
      <Image src="/logo.png" alt="" fill sizes="32px" className="object-contain p-[3px]" />
    </motion.div>
  );
}

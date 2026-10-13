"use client";

import { motion } from "framer-motion";
import { AssistantAvatar } from "./AssistantAvatar";

export function ChatLoadingState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3"
    >
      <AssistantAvatar thinking />
      <div className="flex items-center gap-2.5 rounded-[16px] rounded-tl-[4px] border-2 border-ink bg-card px-5 py-4">
        <span className="text-[13px] text-muted">Thinking through your saved content</span>
        <span className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              animate={{ opacity: [0.2, 1, 0.2] }}
              transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
              className="h-1.5 w-1.5 rounded-full bg-[#FF5C00]"
            />
          ))}
        </span>
      </div>
    </motion.div>
  );
}

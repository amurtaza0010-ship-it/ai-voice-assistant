"use client";

import { motion } from "framer-motion";

export function Waveform({ active }: { active: boolean }) {
  return (
    <div className="flex items-end justify-center gap-1 h-16">
      {Array.from({ length: 24 }).map((_, i) => (
        <motion.div
          key={i}
          className="w-1 rounded-full bg-gradient-to-t from-violet-500 to-cyan-400"
          animate={
            active
              ? { height: [8, 24 + (i % 5) * 8, 12, 32, 10] }
              : { height: 6 }
          }
          transition={
            active
              ? { duration: 0.8, repeat: Infinity, delay: i * 0.04 }
              : { duration: 0.3 }
          }
          style={{ height: 6 }}
        />
      ))}
    </div>
  );
}

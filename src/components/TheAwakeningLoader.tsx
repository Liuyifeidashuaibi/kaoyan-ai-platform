"use client";

/**
 * TheAwakeningLoader — site intro brand reveal (once per session).
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import {
  AWAKENING_EASE,
  AwakeningLogo,
} from "@/components/brand/awakening-logo";

const LOGO_PX = 148;

interface TheAwakeningLoaderProps {
  onComplete?: () => void;
}

export function TheAwakeningLoader({ onComplete }: TheAwakeningLoaderProps) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const schedule: Array<[number, number]> = [
      [300, 1],
      [700, 2],
      [1300, 3],
      [2100, 4],
      [2500, 5],
      [3000, 6],
    ];

    const timers = schedule.map(([ms, ph]) => setTimeout(() => setPhase(ph), ms));
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <AnimatePresence onExitComplete={onComplete}>
      {phase < 6 && (
        <motion.div
          key="awakening"
          className="fixed inset-0 z-[9999] flex items-center justify-center"
          style={{ backgroundColor: "#FAFAFA" }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: AWAKENING_EASE }}
        >
          <AnimatePresence>
            {phase === 1 && (
              <motion.div
                key="dot"
                className="absolute rounded-full"
                style={{
                  width: 7,
                  height: 7,
                  backgroundColor: "#111111",
                }}
                initial={{ opacity: 0, scale: 0.3, filter: "blur(6px)" }}
                animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                exit={{ opacity: 0, scale: 0.3, filter: "blur(6px)" }}
                transition={{ duration: 0.4, ease: AWAKENING_EASE }}
              />
            )}
          </AnimatePresence>

          <AwakeningLogo size={LOGO_PX} introPhase={phase} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

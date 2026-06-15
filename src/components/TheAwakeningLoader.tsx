"use client";

/**
 * TheAwakeningLoader — a brand reveal experience, not a loading spinner.
 *
 * Seven scenes across 3.5 s:
 *   0 → void         pure #FAFAFA stillness
 *   1 → consciousness  a dark point sharpens from blur
 *   2 → discovery     bird body emerges, carved from the void
 *   3 → wings         upper wing expands right, then lower wing follows
 *   4 → recognition   the F inside the bird becomes apparent
 *   5 → energy        an atmospheric light sweep at < 8 % opacity
 *   6 → opening       logo advances 12 px; exit animation reveals content
 */

import { AnimatePresence, motion } from "framer-motion";
import Image from "next/image";
import { useEffect, useState } from "react";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];
const LOGO_PX = 148;

// Clip-path constants — derived from the bird-F silhouette geometry.
// The vertical split at 51 % separates the upper wing from the lower wing.
// The horizontal cut at 44 % isolates the body/head from the wing spans.
const UPPER_BODY = "polygon(0% 0%, 44% 0%, 44% 51%, 0% 51%)";
const UPPER_FULL = "polygon(0% 0%, 100% 0%, 100% 51%, 0% 51%)";
const LOWER_BODY = "polygon(0% 51%, 44% 51%, 44% 100%, 0% 100%)";
const LOWER_FULL = "polygon(0% 51%, 100% 51%, 100% 100%, 0% 100%)";

interface TheAwakeningLoaderProps {
  onComplete?: () => void;
}

export function TheAwakeningLoader({ onComplete }: TheAwakeningLoaderProps) {
  // phase steps through each scene in order
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    // Cumulative ms → phase number
    const schedule: Array<[number, number]> = [
      [300, 1],   // consciousness  (+300 ms after void)
      [700, 2],   // discovery      (+400 ms)
      [1300, 3],  // wing formation (+600 ms)
      [2100, 4],  // recognition    (+800 ms)
      [2500, 5],  // energy pass    (+400 ms)
      [3000, 6],  // opening        (+500 ms  — triggers exit animation)
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
          transition={{ duration: 0.5, ease: EASE }}
        >
          {/* ── Scene 2: consciousness — a single dark point */}
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
                transition={{ duration: 0.4, ease: EASE }}
              />
            )}
          </AnimatePresence>

          {/* ── Scenes 3–7: the logo */}
          <motion.div
            // Outer wrapper: blur-to-sharp reveal on discovery
            style={{ width: LOGO_PX, height: LOGO_PX }}
            initial={{ opacity: 0, filter: "blur(22px)", scale: 1.05 }}
            animate={
              phase >= 2
                ? { opacity: 1, filter: "blur(0px)", scale: 1 }
                : {}
            }
            transition={{ duration: 0.6, ease: EASE }}
          >
            {/* Scene 7: logo advances 12 px forward */}
            <motion.div
              style={{ position: "relative", width: LOGO_PX, height: LOGO_PX }}
              animate={phase >= 5 ? { x: 12 } : { x: 0 }}
              transition={{ duration: 0.6, ease: EASE }}
            >
              {/* ── Upper half — body visible immediately, wing expands right */}
              <motion.div
                style={{ position: "absolute", inset: 0 }}
                initial={{ clipPath: UPPER_BODY }}
                animate={phase >= 3 ? { clipPath: UPPER_FULL } : {}}
                transition={{ duration: 0.75, ease: EASE }}
              >
                <Image
                  src="/logo.png"
                  alt=""
                  width={LOGO_PX}
                  height={LOGO_PX}
                  className="object-contain select-none"
                  priority
                  draggable={false}
                  aria-hidden
                />
              </motion.div>

              {/* ── Lower half — follows upper wing with a 260 ms delay */}
              <motion.div
                style={{ position: "absolute", inset: 0 }}
                initial={{ clipPath: LOWER_BODY }}
                animate={phase >= 3 ? { clipPath: LOWER_FULL } : {}}
                transition={{ duration: 0.75, ease: EASE, delay: 0.26 }}
              >
                <Image
                  src="/logo.png"
                  alt=""
                  width={LOGO_PX}
                  height={LOGO_PX}
                  className="object-contain select-none"
                  priority
                  draggable={false}
                  aria-hidden
                />
              </motion.div>

              {/* ── Scene 6: energy pass — atmospheric light sweep < 8 % opacity */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  overflow: "hidden",
                  pointerEvents: "none",
                }}
              >
                <motion.div
                  style={{
                    position: "absolute",
                    top: 0,
                    bottom: 0,
                    width: "70%",
                    background:
                      "linear-gradient(105deg, transparent 20%, rgba(255,255,255,0.07) 50%, transparent 80%)",
                  }}
                  initial={{ left: "-70%" }}
                  animate={phase >= 5 ? { left: "160%" } : { left: "-70%" }}
                  transition={{ duration: 0.5, ease: EASE }}
                />
              </div>
            </motion.div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

"use client";

/**
 * Translation loading — infinite loop built on the same black logo
 * clip-path wing animation as the site intro (TheAwakeningLoader).
 */

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import {
  AWAKENING_EASE,
  AwakeningLogo,
} from "@/components/brand/awakening-logo";
import { cn } from "@/lib/utils";

const LOGO_PX = 120;
const LOOP_SECONDS = 8;

const STATUS_MESSAGES = [
  "Analyzing source…",
  "Detecting language…",
  "AI translation in progress…",
  "Refining output…",
];

const INFLOW_SYMBOLS = [
  { char: "A", y: -28 },
  { char: "Σ", y: -8 },
  { char: "あ", y: 12 },
  { char: "Bn", y: 32 },
];

const OUTFLOW_SYMBOLS = [
  { char: "En", y: -24 },
  { char: "Zh", y: -4 },
  { char: "→", y: 16 },
  { char: "Ω", y: 36 },
];

const ORBIT_DOTS = Array.from({ length: 8 }, (_, i) => ({
  id: i,
  radius: 68 + (i % 3) * 12,
  duration: 5 + (i % 4) * 0.5,
  delay: i * 0.4,
  size: i % 2 === 0 ? 3 : 2,
}));

type TranslationLoadingAnimationProps = {
  className?: string;
  compact?: boolean;
  message?: string;
};

export function TranslationLoadingAnimation({
  className,
  compact = false,
  message,
}: TranslationLoadingAnimationProps) {
  const reduceMotion = useReducedMotion();
  const [statusIndex, setStatusIndex] = useState(0);

  const logoSize = compact ? 88 : LOGO_PX;
  const stageSize = compact ? 210 : 280;

  useEffect(() => {
    const interval = window.setInterval(() => {
      setStatusIndex((i) => (i + 1) % STATUS_MESSAGES.length);
    }, 2500);
    return () => window.clearInterval(interval);
  }, []);

  const statusText = message ?? STATUS_MESSAGES[statusIndex];

  const streamPaths = useMemo(
    () => [
      "M 18 88 Q 70 72 128 96",
      "M 12 128 Q 68 118 128 128",
      "M 20 168 Q 72 152 128 160",
      "M 152 96 Q 208 80 262 96",
      "M 152 128 Q 210 118 262 128",
      "M 152 160 Q 208 148 262 164",
    ],
    []
  );

  if (reduceMotion) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-3",
          className
        )}
        role="status"
        aria-live="polite"
        aria-label={statusText}
      >
        <AwakeningLogo size={logoSize} introPhase={4} />
        <p className="text-muted-foreground text-sm tracking-wide">{statusText}</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center",
        className
      )}
      role="status"
      aria-live="polite"
      aria-label={statusText}
    >
      <div
        className="relative"
        style={{ width: stageSize, height: stageSize }}
      >
        {/* Ambient glow — matches intro #111111 tone */}
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            width: logoSize * 1.65,
            height: logoSize * 1.65,
            background:
              "radial-gradient(circle, rgba(17,17,17,0.07) 0%, transparent 72%)",
          }}
          animate={{ scale: [1, 1.1, 1], opacity: [0.45, 0.8, 0.45] }}
          transition={{
            duration: LOOP_SECONDS / 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />

        {/* Data streams */}
        <svg
          className="pointer-events-none absolute inset-0 size-full overflow-visible"
          viewBox="0 0 280 256"
          fill="none"
          aria-hidden
        >
          {streamPaths.map((d, i) => (
            <motion.path
              key={d}
              d={d}
              stroke="#111111"
              strokeWidth={1}
              strokeOpacity={0.1}
              strokeLinecap="round"
              animate={{
                pathLength: [0.12, 1, 0.12],
                opacity: [0.06, 0.2, 0.06],
              }}
              transition={{
                duration: LOOP_SECONDS,
                repeat: Infinity,
                delay: i * 0.22,
                ease: "easeInOut",
              }}
            />
          ))}
          {streamPaths.slice(0, 3).map((d, i) => (
            <circle key={`in-${i}`} r={2} fill="#111111" fillOpacity={0.22}>
              <animateMotion
                dur={`${LOOP_SECONDS}s`}
                repeatCount="indefinite"
                begin={`${i * 0.85}s`}
                path={d}
              />
              <animate
                attributeName="opacity"
                values="0;0.85;0"
                dur={`${LOOP_SECONDS}s`}
                repeatCount="indefinite"
                begin={`${i * 0.85}s`}
              />
            </circle>
          ))}
          {streamPaths.slice(3).map((d, i) => (
            <circle key={`out-${i}`} r={2} fill="#111111" fillOpacity={0.32}>
              <animateMotion
                dur={`${LOOP_SECONDS}s`}
                repeatCount="indefinite"
                begin={`${i * 0.85 + LOOP_SECONDS * 0.18}s`}
                path={d}
              />
              <animate
                attributeName="opacity"
                values="0;0.95;0"
                dur={`${LOOP_SECONDS}s`}
                repeatCount="indefinite"
                begin={`${i * 0.85 + LOOP_SECONDS * 0.18}s`}
              />
            </circle>
          ))}
        </svg>

        {/* Orbital particles */}
        {ORBIT_DOTS.map((dot) => (
          <motion.div
            key={dot.id}
            className="pointer-events-none absolute left-1/2 top-1/2"
            style={{
              width: dot.radius * 2,
              height: dot.radius * 2,
              marginLeft: -dot.radius,
              marginTop: -dot.radius,
            }}
            animate={{ rotate: 360 }}
            transition={{
              duration: dot.duration,
              repeat: Infinity,
              ease: "linear",
              delay: dot.delay,
            }}
          >
            <span
              className="absolute left-1/2 top-0 block rounded-full bg-[#111111]/18"
              style={{
                width: dot.size,
                height: dot.size,
                marginLeft: -dot.size / 2,
              }}
            />
          </motion.div>
        ))}

        {/* Language inflow */}
        {INFLOW_SYMBOLS.map((item, i) => (
          <motion.span
            key={`in-${item.char}`}
            className="pointer-events-none absolute left-1/2 top-1/2 text-[11px] font-medium text-[#111111]/35"
            style={{ marginTop: item.y }}
            animate={{
              x: [-stageSize * 0.4, -logoSize * 0.2, 0],
              opacity: [0, 0.7, 0],
              filter: ["blur(4px)", "blur(0px)", "blur(5px)"],
              scale: [0.85, 1, 0.55],
            }}
            transition={{
              duration: LOOP_SECONDS * 0.75,
              repeat: Infinity,
              delay: i * (LOOP_SECONDS / INFLOW_SYMBOLS.length) * 0.48,
              ease: AWAKENING_EASE,
            }}
          >
            {item.char}
          </motion.span>
        ))}

        {/* Language outflow */}
        {OUTFLOW_SYMBOLS.map((item, i) => (
          <motion.span
            key={`out-${item.char}`}
            className="pointer-events-none absolute left-1/2 top-1/2 text-[11px] font-medium text-[#111111]/55"
            style={{ marginTop: item.y }}
            animate={{
              x: [0, logoSize * 0.26, stageSize * 0.4],
              opacity: [0, 0.85, 0],
              filter: ["blur(5px)", "blur(0px)", "blur(2px)"],
              scale: [0.55, 1, 0.88],
            }}
            transition={{
              duration: LOOP_SECONDS * 0.75,
              repeat: Infinity,
              delay:
                i * (LOOP_SECONDS / OUTFLOW_SYMBOLS.length) * 0.48 +
                LOOP_SECONDS * 0.16,
              ease: AWAKENING_EASE,
            }}
          >
            {item.char}
          </motion.span>
        ))}

        {/* Core logo — same clip-path wing system as site intro */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <AwakeningLogo size={logoSize} loop />
        </div>

        {/* Processing ring */}
        <motion.div
          className="pointer-events-none absolute left-1/2 top-1/2 rounded-full border border-[#111111]/10"
          style={{
            width: logoSize * 1.38,
            height: logoSize * 1.38,
            marginLeft: -(logoSize * 1.38) / 2,
            marginTop: -(logoSize * 1.38) / 2,
          }}
          animate={{ rotate: 360, opacity: [0.3, 0.6, 0.3] }}
          transition={{
            rotate: { duration: 14, repeat: Infinity, ease: "linear" },
            opacity: {
              duration: LOOP_SECONDS / 2,
              repeat: Infinity,
              ease: "easeInOut",
            },
          }}
        />
      </div>

      <motion.p
        key={statusText}
        className="text-muted-foreground mt-2 text-center text-sm tracking-wide"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: AWAKENING_EASE }}
      >
        {statusText}
      </motion.p>
    </div>
  );
}

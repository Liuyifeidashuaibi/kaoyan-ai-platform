"use client";

/**
 * Shared PNIXPG logo mark — black bird-F with clip-path wing reveal.
 * Used by site intro (TheAwakeningLoader) and translation loading loop.
 */

import { motion, type Transition } from "framer-motion";
import Image from "next/image";

import { cn } from "@/lib/utils";

export const AWAKENING_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const LOGO_CLIP = {
  UPPER_BODY: "polygon(0% 0%, 44% 0%, 44% 51%, 0% 51%)",
  UPPER_FULL: "polygon(0% 0%, 100% 0%, 100% 51%, 0% 51%)",
  LOWER_BODY: "polygon(0% 51%, 44% 51%, 44% 100%, 0% 100%)",
  LOWER_FULL: "polygon(0% 51%, 100% 51%, 100% 100%, 0% 100%)",
  UPPER_PULSE: "polygon(0% 0%, 90% 0%, 90% 51%, 0% 51%)",
  LOWER_PULSE: "polygon(0% 51%, 90% 51%, 90% 100%, 0% 100%)",
} as const;

const LOOP_SECONDS = 8;

type AwakeningLogoProps = {
  size: number;
  /** Site intro — driven by phase 0–6 */
  introPhase?: number;
  /** Infinite translation / processing loop */
  loop?: boolean;
  className?: string;
};

function LogoImage({ size }: { size: number }) {
  return (
    <Image
      src="/logo.png"
      alt=""
      width={size}
      height={size}
      className="object-contain select-none mix-blend-darken"
      priority
      draggable={false}
      aria-hidden
    />
  );
}

function EnergySweep({ loop }: { loop?: boolean }) {
  const transition: Transition = loop
    ? { duration: LOOP_SECONDS, repeat: Infinity, ease: AWAKENING_EASE }
    : { duration: 0.5, ease: AWAKENING_EASE };

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden"
      aria-hidden
    >
      <motion.div
        className="absolute inset-y-0 w-[70%]"
        style={{
          background:
            "linear-gradient(105deg, transparent 20%, rgba(255,255,255,0.08) 50%, transparent 80%)",
        }}
        initial={{ left: "-70%" }}
        animate={{ left: loop ? ["-70%", "160%", "-70%"] : "160%" }}
        transition={transition}
      />
    </div>
  );
}

export function AwakeningLogo({
  size,
  introPhase = 0,
  loop = false,
  className,
}: AwakeningLogoProps) {
  const wingsRevealed = loop || introPhase >= 3;
  const energyActive = loop || introPhase >= 5;
  const forwardShift = loop ? undefined : introPhase >= 5;

  const upperClip = loop
    ? { clipPath: [LOGO_CLIP.UPPER_FULL, LOGO_CLIP.UPPER_PULSE, LOGO_CLIP.UPPER_FULL] }
    : wingsRevealed
      ? { clipPath: LOGO_CLIP.UPPER_FULL }
      : { clipPath: LOGO_CLIP.UPPER_BODY };

  const lowerClip = loop
    ? { clipPath: [LOGO_CLIP.LOWER_FULL, LOGO_CLIP.LOWER_PULSE, LOGO_CLIP.LOWER_FULL] }
    : wingsRevealed
      ? { clipPath: LOGO_CLIP.LOWER_FULL }
      : { clipPath: LOGO_CLIP.LOWER_BODY };

  const wingTransition: Transition = loop
    ? {
        duration: LOOP_SECONDS / 2,
        repeat: Infinity,
        ease: "easeInOut",
        delay: 0.26,
      }
    : { duration: 0.75, ease: AWAKENING_EASE };

  const lowerWingTransition: Transition = loop
    ? {
        duration: LOOP_SECONDS / 2,
        repeat: Infinity,
        ease: "easeInOut",
        delay: 0.52,
      }
    : { duration: 0.75, ease: AWAKENING_EASE, delay: 0.26 };

  const logoBody = (
    <motion.div
      className="relative"
      style={{ width: size, height: size }}
      animate={
        loop
          ? {
              y: [0, -6, 0],
              scale: [1, 1.035, 1],
              x: [0, 4, 0],
            }
          : forwardShift
            ? { x: 12 }
            : { x: 0 }
      }
      transition={
        loop
          ? {
              duration: LOOP_SECONDS / 2,
              repeat: Infinity,
              ease: "easeInOut",
            }
          : { duration: 0.6, ease: AWAKENING_EASE }
      }
    >
      <motion.div
        className="absolute inset-0"
        initial={{ clipPath: loop ? LOGO_CLIP.UPPER_FULL : LOGO_CLIP.UPPER_BODY }}
        animate={upperClip}
        transition={wingTransition}
      >
        <LogoImage size={size} />
      </motion.div>

      <motion.div
        className="absolute inset-0"
        initial={{ clipPath: loop ? LOGO_CLIP.LOWER_FULL : LOGO_CLIP.LOWER_BODY }}
        animate={lowerClip}
        transition={lowerWingTransition}
      >
        <LogoImage size={size} />
      </motion.div>

      {energyActive && <EnergySweep loop={loop} />}
    </motion.div>
  );

  if (loop) {
    return (
      <div className={cn("relative", className)} style={{ width: size, height: size }}>
        {logoBody}
      </div>
    );
  }

  return (
    <motion.div
      className={cn("relative", className)}
      style={{ width: size, height: size }}
      initial={{ opacity: 0, filter: "blur(22px)", scale: 1.05 }}
      animate={
        introPhase >= 2
          ? { opacity: 1, filter: "blur(0px)", scale: 1 }
          : { opacity: 0, filter: "blur(22px)", scale: 1.05 }
      }
      transition={{ duration: 0.6, ease: AWAKENING_EASE }}
    >
      {logoBody}
    </motion.div>
  );
}

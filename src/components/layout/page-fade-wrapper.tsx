"use client";

/**
 * PageFadeWrapper — smooth page-content transitions on every App Router navigation.
 *
 * Keyed to the current pathname: each navigation re-mounts the inner motion.main,
 * producing a crisp fade-in (and a matching fade-out via AnimatePresence).
 *
 * The component inherits the exact layout classes that used to live on the
 * static <main> element inside AppShell so that visual layout is unchanged.
 */

import { AnimatePresence, motion } from "framer-motion";
import { usePathname } from "next/navigation";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

interface PageFadeWrapperProps {
  children: React.ReactNode;
  className?: string;
}

export function PageFadeWrapper({ children, className }: PageFadeWrapperProps) {
  const pathname = usePathname();

  return (
    // mode="popLayout" removes the exiting page from layout flow immediately,
    // so the entering page takes its natural position without overlap jank.
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.main
        key={pathname}
        className={className}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.2, ease: EASE }}
      >
        {children}
      </motion.main>
    </AnimatePresence>
  );
}

"use client";

/**
 * Main content shell — stable wrapper without remounting the layout tree.
 * Route transitions rely on Next.js page swaps; a light CSS fade avoids
 * framer-motion + AnimatePresence cost on every navigation.
 */

import { usePathname } from "next/navigation";

interface PageFadeWrapperProps {
  children: React.ReactNode;
  className?: string;
}

export function PageFadeWrapper({ children, className }: PageFadeWrapperProps) {
  const pathname = usePathname();

  return (
    <main className={className}>
      <div
        key={pathname}
        className="h-full min-h-0 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1 motion-safe:duration-200"
      >
        {children}
      </div>
    </main>
  );
}

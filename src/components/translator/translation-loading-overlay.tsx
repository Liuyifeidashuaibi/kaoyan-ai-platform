"use client";

import { AnimatePresence, motion } from "framer-motion";

import { TranslationLoadingAnimation } from "@/components/translator/translation-loading-animation";

type TranslationLoadingOverlayProps = {
  open: boolean;
};

export function TranslationLoadingOverlay({ open }: TranslationLoadingOverlayProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="translation-loading"
          className="absolute inset-0 z-20 flex items-center justify-center bg-background/75 backdrop-blur-[2px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          aria-hidden={!open}
        >
          <TranslationLoadingAnimation />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

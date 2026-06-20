"use client";

import dynamic from "next/dynamic";

import { TranslationLoadingAnimation } from "@/components/translator/translation-loading-animation";

const TranslatorApp = dynamic(
  () =>
    import("@/components/translator/translator-app").then(
      (mod) => mod.TranslatorApp
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[50vh] items-center justify-center p-8">
        <TranslationLoadingAnimation compact message="Loading…" />
      </div>
    ),
  }
);

export function TranslatorPageClient() {
  return <TranslatorApp />;
}

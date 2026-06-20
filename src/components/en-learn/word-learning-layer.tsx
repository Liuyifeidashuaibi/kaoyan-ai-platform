"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { queryWord, type WordDetail } from "@/lib/api/word-query";
import { cn } from "@/lib/utils";

type TooltipState = {
  word: string;
  rect: DOMRect;
  phonetic: string | null;
  pos: string | null;
  gloss: string;
  loading?: boolean;
  error?: string;
};

type WordLearningContextValue = {
  enabled: boolean;
  onWordEnter: (word: string, el: HTMLElement) => void;
  onWordLeave: (word: string) => void;
  onWordClick: (word: string) => void;
};

const WordLearningContext = createContext<WordLearningContextValue | null>(null);

export function WordLearningProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [detail, setDetail] = useState<WordDetail | null>(null);
  const cache = useRef<Map<string, Omit<TooltipState, "rect">>>(new Map());
  const pending = useRef<string | null>(null);
  const hoverWord = useRef<string | null>(null);
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const lookup = useCallback(async (word: string, el: HTMLElement) => {
    const key = word.toLowerCase();
    const rect = el.getBoundingClientRect();
    const cached = cache.current.get(key);
    if (cached && !cached.error) {
      setTooltip({ ...cached, word, rect });
      return;
    }

    pending.current = key;
    setTooltip({
      word,
      rect,
      phonetic: null,
      pos: null,
      gloss: "",
      loading: true,
    });

    try {
      const data = await queryWord(word, "hover");
      if (pending.current !== key || hoverWord.current !== key) return;

      if (data.source === "missing" || !data.gloss?.trim()) {
        const miss = {
          word,
          phonetic: null,
          pos: null,
          gloss: "",
          error: "No definition · click for more",
        };
        cache.current.set(key, miss);
        setTooltip({ ...miss, rect: el.getBoundingClientRect() });
        return;
      }

      const item = {
        word: data.word,
        phonetic: data.phonetic,
        pos: data.pos,
        gloss: data.gloss,
      };
      cache.current.set(key, item);
      setTooltip({ ...item, rect: el.getBoundingClientRect() });
    } catch (e) {
      if (pending.current !== key || hoverWord.current !== key) return;
      const msg = e instanceof Error ? e.message : "Lookup failed";
      const isTimeout = msg.includes("timeout") || msg.includes("Timeout");
      const item = {
        word,
        phonetic: null,
        pos: null,
        gloss: "",
        error: isTimeout ? "No definition · click for more" : msg,
      };
      setTooltip({ ...item, rect: el.getBoundingClientRect() });
    }
  }, []);

  const onWordEnter = useCallback(
    (word: string, el: HTMLElement) => {
      if (!enabled) return;
      if (leaveTimer.current) {
        clearTimeout(leaveTimer.current);
        leaveTimer.current = null;
      }
      hoverWord.current = word.toLowerCase();
      void lookup(word, el);
    },
    [enabled, lookup]
  );

  const onWordLeave = useCallback((word: string) => {
    if (leaveTimer.current) clearTimeout(leaveTimer.current);
    leaveTimer.current = setTimeout(() => {
      if (hoverWord.current === word.toLowerCase()) {
        hoverWord.current = null;
        pending.current = null;
        setTooltip(null);
      }
    }, 120);
  }, []);

  const onWordClick = useCallback(async (word: string) => {
    setDetail({
      word,
      phonetic: null,
      pos: null,
      gloss: "Loading…",
      source: "loading",
      translation: null,
      definition: null,
      tag: null,
      collins: null,
      oxford: null,
      exchange: null,
      detail: null,
      kaoyan_gloss: null,
      kaoyan_phrases: [],
    });
    try {
      const data = (await queryWord(word, "detail")) as WordDetail;
      setDetail(data);
      setTooltip(null);
    } catch (e) {
      setDetail({
        word,
        phonetic: null,
        pos: null,
        gloss: e instanceof Error ? e.message : "Word not found",
        source: "none",
        translation: null,
        definition: null,
        tag: null,
        collins: null,
        oxford: null,
        exchange: null,
        detail: null,
        kaoyan_gloss: null,
        kaoyan_phrases: [],
      });
    }
  }, []);

  const ctx: WordLearningContextValue = {
    enabled,
    onWordEnter,
    onWordLeave,
    onWordClick,
  };

  return (
    <WordLearningContext.Provider value={ctx}>
      {children}
      {enabled && tooltip && (
        <div
          className="pointer-events-none fixed z-[100] max-w-[240px] rounded-md border bg-popover px-2.5 py-2 text-xs shadow-lg"
          style={{
            left: Math.min(tooltip.rect.left, window.innerWidth - 260),
            top: tooltip.rect.bottom + 6,
          }}
        >
          <div className="font-medium">{tooltip.word}</div>
          {tooltip.loading ? (
            <div className="text-muted-foreground mt-1">Looking up…</div>
          ) : tooltip.error ? (
            <div className="text-muted-foreground mt-1">{tooltip.error}</div>
          ) : (
            <>
              {(tooltip.phonetic || tooltip.pos) && (
                <div className="text-muted-foreground font-mono text-[11px]">
                  {[tooltip.phonetic, tooltip.pos].filter(Boolean).join(" · ")}
                </div>
              )}
              <div className="mt-0.5 leading-relaxed">{tooltip.gloss}</div>
            </>
          )}
        </div>
      )}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-h-[70vh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{detail?.word}</DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-2 text-sm">
              <p className="text-muted-foreground">
                {[detail.phonetic, detail.pos].filter(Boolean).join(" · ")}
              </p>
              <p className="font-medium">
                {detail.kaoyan_gloss ?? detail.gloss ?? "No definition"}
              </p>
              {detail.translation && (
                <div className="space-y-1 text-xs">
                  <p className="text-muted-foreground font-medium">More meanings</p>
                  <pre className="whitespace-pre-wrap">{detail.translation}</pre>
                </div>
              )}
              {detail.kaoyan_phrases?.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium">Example phrases</p>
                  <ul className="list-inside list-disc text-xs">
                    {detail.kaoyan_phrases.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
              {detail.source && detail.source !== "loading" && detail.source !== "none" && (
                <p className="text-muted-foreground text-[11px]">
                  {detail.source === "local" || detail.source === "ai_cache"
                    ? "Source: dictionary"
                    : detail.source === "ai"
                      ? "Source: online supplement"
                      : null}
                </p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </WordLearningContext.Provider>
  );
}

export function LearningWord({
  word,
  className,
  children,
}: {
  word: string;
  className?: string;
  children: ReactNode;
}) {
  const ctx = useContext(WordLearningContext);
  if (!ctx?.enabled) {
    return <span className={className}>{children}</span>;
  }
  const key = word.toLowerCase();
  return (
    <span
      className={cn(className, "cursor-pointer rounded-sm hover:bg-primary/10")}
      onMouseEnter={(e) => ctx.onWordEnter(key, e.currentTarget)}
      onMouseLeave={() => ctx.onWordLeave(key)}
      onClick={(e) => {
        e.stopPropagation();
        void ctx.onWordClick(key);
      }}
    >
      {children}
    </span>
  );
}

/** @deprecated use WordLearningProvider */
export function WordLearningLayer({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  return (
    <WordLearningProvider enabled={enabled}>
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </WordLearningProvider>
  );
}

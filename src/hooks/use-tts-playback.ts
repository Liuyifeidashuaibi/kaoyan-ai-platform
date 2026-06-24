"use client";

import { useCallback, useRef, useState } from "react";

import { synthesizeTtsWav, type TtsOptions } from "@/lib/api/tts";

export type TtsPlaybackState = {
  options: TtsOptions;
  setOptions: React.Dispatch<React.SetStateAction<TtsOptions>>;
  busy: boolean;
  playing: boolean;
  status: string | null;
  selectedLineIndex: number | null;
  playingLineIndex: number | null;
  selectLine: (index: number | null) => void;
  playText: (text: string, lineIndex?: number | null) => Promise<void>;
  stop: () => void;
};

type UseTtsPlaybackOptions = {
  onHighlightIndex?: (index: number | null) => void;
  onError?: (message: string | null) => void;
};

async function playBlob(
  blob: Blob,
  audioRef: React.MutableRefObject<HTMLAudioElement | null>
) {
  const url = URL.createObjectURL(blob);
  try {
    await new Promise<void>((resolve, reject) => {
      const audio = new Audio(url);
      audio.volume = 1;
      audioRef.current = audio;
      audio.onended = () => resolve();
      audio.onerror = () => reject(new Error("Audio playback failed"));
      void audio.play().catch(reject);
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function useTtsPlayback({
  onHighlightIndex,
  onError,
}: UseTtsPlaybackOptions = {}): TtsPlaybackState {
  const [options, setOptions] = useState<TtsOptions>({
    accent: "us",
    speed: 1,
    voice: "female",
  });
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [selectedLineIndex, setSelectedLineIndex] = useState<number | null>(null);
  const [playingLineIndex, setPlayingLineIndex] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const stopRef = useRef(false);

  const stop = useCallback(() => {
    stopRef.current = true;
    audioRef.current?.pause();
    audioRef.current = null;
    setBusy(false);
    setPlaying(false);
    setStatus(null);
    setPlayingLineIndex(null);
    onHighlightIndex?.(null);
  }, [onHighlightIndex]);

  const playText = useCallback(
    async (text: string, lineIndex: number | null = null) => {
      const content = text.trim();
      if (!content || busy || playing) return;

      stopRef.current = false;
      setBusy(true);
      setPlaying(true);
      setPlayingLineIndex(lineIndex);
      onError?.(null);
      setStatus("Synthesizing…");
      onHighlightIndex?.(lineIndex ?? 0);

      try {
        const blob = await synthesizeTtsWav(content, options);
        if (stopRef.current) return;
        if (!blob.size) throw new Error("Empty audio");
        setBusy(false);
        setStatus("Playing…");
        await playBlob(blob, audioRef);
      } catch (e) {
        onError?.(e instanceof Error ? e.message : "Read aloud failed");
      } finally {
        onHighlightIndex?.(null);
        setStatus(null);
        setBusy(false);
        setPlaying(false);
        setPlayingLineIndex(null);
        audioRef.current = null;
      }
    },
    [busy, playing, onError, onHighlightIndex, options]
  );

  const selectLine = useCallback((index: number | null) => {
    setSelectedLineIndex(index);
  }, []);

  return {
    options,
    setOptions,
    busy,
    playing,
    status,
    selectedLineIndex,
    playingLineIndex,
    selectLine,
    playText,
    stop,
  };
}

/** 与后端 split_tts_sentences 一致的分句 */
export function splitEnglishLines(text: string): string[] {
  const stripped = text.trim();
  if (!stripped) return [];
  const parts = stripped
    .split(/(?<=[.!?])\s+/)
    .map((p) => p.trim())
    .filter(Boolean);
  return parts.length > 0 ? parts : [stripped];
}

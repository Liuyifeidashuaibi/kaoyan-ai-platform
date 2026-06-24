"use client";

import { Pause, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { TtsPlaybackState } from "@/hooks/use-tts-playback";
import { cn } from "@/lib/utils";

type Props = {
  text: string;
  disabled?: boolean;
  variant?: "bar" | "inline";
  playback: TtsPlaybackState;
};

function SegmentedToggle<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex rounded-md border bg-background p-0.5",
        className
      )}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={cn(
            "rounded px-2 py-0.5 text-[11px] font-medium transition-colors",
            value === opt.value
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function TtsReadAloudBar({
  text,
  disabled,
  variant = "inline",
  playback,
}: Props) {
  const { options, setOptions, busy, playing, playText, stop } = playback;

  const controls = (
    <div className="flex flex-wrap items-center gap-1.5">
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        disabled={disabled || busy || playing || !text.trim()}
        onClick={() => void playText(text, null)}
      >
        Read
      </Button>
      {(busy || playing) && (
        <Button
          size="icon-sm"
          variant="ghost"
          className="size-7"
          title="Stop"
          aria-label="Stop"
          onClick={stop}
        >
          <Pause className="size-3.5" />
        </Button>
      )}
      <SegmentedToggle
        value={String(options.speed)}
        options={[
          { value: "0.8", label: "0.8x" },
          { value: "1", label: "1x" },
          { value: "1.2", label: "1.2x" },
        ]}
        onChange={(v) => setOptions((o) => ({ ...o, speed: Number(v) }))}
      />
      <SegmentedToggle
        value={options.accent}
        options={[
          { value: "us", label: "US" },
          { value: "uk", label: "UK" },
        ]}
        onChange={(accent) => setOptions((o) => ({ ...o, accent }))}
      />
      <SegmentedToggle
        value={options.voice}
        options={[
          { value: "female", label: "F" },
          { value: "male", label: "M" },
        ]}
        onChange={(voice) => setOptions((o) => ({ ...o, voice }))}
      />
    </div>
  );

  if (variant === "bar") {
    return (
      <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-2 py-1.5">
        {controls}
      </div>
    );
  }

  return controls;
}

type LineReadButtonProps = {
  lineIndex: number;
  text: string;
  playback: TtsPlaybackState;
  visible: boolean;
};

/** Speaker icon shown when a line is selected */
export function TtsLineReadButton({
  lineIndex,
  text,
  playback,
  visible,
}: LineReadButtonProps) {
  if (!visible) return null;

  const { busy, playing, playingLineIndex, playText, stop } = playback;
  const isThisLine = playingLineIndex === lineIndex;
  const isActive = isThisLine && (busy || playing);

  return (
    <Button
      type="button"
      size="icon-sm"
      variant="ghost"
      className="size-7 shrink-0"
      title={isActive ? "Stop" : "Read"}
      aria-label={isActive ? "Stop" : "Read"}
      disabled={!text.trim() || (playing && !isThisLine)}
      onClick={(e) => {
        e.stopPropagation();
        if (isActive) {
          stop();
          return;
        }
        void playText(text, lineIndex);
      }}
    >
      {isActive ? (
        <Pause className="size-3.5" />
      ) : (
        <Volume2 className="size-3.5" />
      )}
    </Button>
  );
}

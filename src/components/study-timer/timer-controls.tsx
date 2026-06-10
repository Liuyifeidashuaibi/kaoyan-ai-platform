import { Button } from "@/components/ui/button";

interface TimerControlsProps {
  isRunning: boolean;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
}

export function TimerControls({
  isRunning,
  onStart,
  onPause,
  onReset,
}: TimerControlsProps) {
  return (
    <div className="flex flex-wrap justify-center gap-3">
      {isRunning ? (
        <Button type="button" variant="secondary" onClick={onPause}>
          暂停
        </Button>
      ) : (
        <Button type="button" onClick={onStart}>
          开始
        </Button>
      )}
      <Button type="button" variant="outline" onClick={onReset}>
        重置
      </Button>
    </div>
  );
}

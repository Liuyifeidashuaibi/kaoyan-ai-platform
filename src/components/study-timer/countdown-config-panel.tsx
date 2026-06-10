import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  COUNTDOWN_MAX_MINUTES,
  COUNTDOWN_MIN_MINUTES,
  COUNTDOWN_PRESETS_MINUTES,
} from "@/lib/study-timer/constants";

interface CountdownConfigPanelProps {
  minutes: number;
  onChange: (minutes: number) => void;
}

export function CountdownConfigPanel({
  minutes,
  onChange,
}: CountdownConfigPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>倒计时时长</CardTitle>
        <CardDescription>
          选择预设或自定义（{COUNTDOWN_MIN_MINUTES}–{COUNTDOWN_MAX_MINUTES} 分钟）
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {COUNTDOWN_PRESETS_MINUTES.map((preset) => (
            <Button
              key={preset}
              type="button"
              size="sm"
              variant={minutes === preset ? "default" : "outline"}
              onClick={() => onChange(preset)}
            >
              {preset} 分钟
            </Button>
          ))}
        </div>
        <div className="flex items-end gap-3">
          <div className="space-y-2">
            <Label htmlFor="custom-minutes">自定义（分钟）</Label>
            <Input
              id="custom-minutes"
              type="number"
              min={COUNTDOWN_MIN_MINUTES}
              max={COUNTDOWN_MAX_MINUTES}
              value={minutes}
              onChange={(event) => {
                const parsed = Number(event.target.value);
                if (Number.isNaN(parsed)) {
                  return;
                }
                const clamped = Math.min(
                  COUNTDOWN_MAX_MINUTES,
                  Math.max(COUNTDOWN_MIN_MINUTES, Math.floor(parsed))
                );
                onChange(clamped);
              }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

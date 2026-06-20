import { getAuthHeaders } from "@/lib/api/auth-fetch";
import { ensureApiBaseUrl } from "@/lib/config/api";

export type TtsSentence = {
  index: number;
  text: string;
  start_char: number;
  end_char: number;
};

export type TtsOptions = {
  accent: "us" | "uk";
  speed: number;
  voice: "male" | "female";
};

async function readTtsError(res: Response): Promise<string> {
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    try {
      const json = (await res.json()) as { message?: string; detail?: string };
      return json.message || json.detail || "TTS 合成失败";
    } catch {
      return "TTS 合成失败";
    }
  }
  const text = (await res.text()).trim();
  return text || "TTS 合成失败";
}

export async function synthesizeTtsWav(
  text: string,
  options: TtsOptions
): Promise<Blob> {
  const base = await ensureApiBaseUrl();
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${base}/api/tts/synthesize`, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: JSON.stringify({ text, ...options }),
    signal: AbortSignal.timeout(60_000),
  });
  const ct = res.headers.get("content-type") ?? "";
  if (!res.ok) {
    throw new Error(await readTtsError(res));
  }
  if (!ct.includes("audio")) {
    throw new Error(await readTtsError(res));
  }
  const blob = await res.blob();
  if (!blob.size) throw new Error("音频为空");
  return blob;
}

export async function fetchTtsSentences(text: string): Promise<TtsSentence[]> {
  const base = await ensureApiBaseUrl();
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${base}/api/tts/sentences`, {
    method: "POST",
    headers: { ...authHeaders, "Content-Type": "application/json" },
    body: JSON.stringify({ text, accent: "us", speed: 1, voice: "female" }),
  });
  const json = await res.json();
  if (!json.success) throw new Error(json.message ?? "分句失败");
  return json.data ?? [];
}

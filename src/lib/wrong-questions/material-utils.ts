import type { MaterialFileType } from "@/lib/api/types";

export const MATERIAL_TYPE_LABELS: Record<MaterialFileType, string> = {
  image: "图片",
  video: "视频",
  document: "文档",
  audio: "音频",
  other: "其他",
};

export const MATERIAL_TYPE_FILTERS: Array<{
  value: MaterialFileType | "all";
  label: string;
}> = [
  { value: "all", label: "全部" },
  { value: "image", label: "图片" },
  { value: "video", label: "视频" },
  { value: "document", label: "文档" },
  { value: "audio", label: "音频" },
];

export const UPLOAD_ACCEPT =
  "image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv,.mp4,.webm,.mov,.avi,.mkv,.mp3,.wav,.m4a,.ogg";

export function getMaterialPath(item: {
  file_path?: string;
  image_path: string;
}): string {
  return item.file_path || item.image_path;
}

export function formatMaterialTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;

  const pad = (value: number) => String(value).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function isPreviewableImage(type: MaterialFileType): boolean {
  return type === "image";
}

export function isPreviewableVideo(type: MaterialFileType): boolean {
  return type === "video";
}

export function isPreviewableAudio(type: MaterialFileType): boolean {
  return type === "audio";
}

export function isPdfDocument(
  type: MaterialFileType,
  filename?: string | null
): boolean {
  if (type !== "document") return false;
  return (filename || "").toLowerCase().endsWith(".pdf");
}

import type { CommunityAttachment } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";

const IMAGE_MIME_PREFIX = "image/";
const IMAGE_EXT = /\.(jpe?g|png|gif|webp|bmp|svg)$/i;

export function isImageAttachment(att: CommunityAttachment): boolean {
  if (att.mime_type?.startsWith(IMAGE_MIME_PREFIX)) return true;
  return IMAGE_EXT.test(att.name || att.url);
}

export function getImageAttachments(attachments: CommunityAttachment[] = []) {
  return attachments.filter(isImageAttachment);
}

/** 列表预览：正文截断 */
export function truncatePostContent(content: string, maxLen = 120): string {
  const normalized = content.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLen) return normalized;
  return `${normalized.slice(0, maxLen).trimEnd()}…`;
}

export function attachmentPreviewUrl(att: CommunityAttachment): string {
  return resolveUploadUrl(att.url);
}

export const PREVIEW_IMAGE_COUNT = 3;

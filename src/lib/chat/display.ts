const IMAGE_OCR_MARKER = "[图片内容]";
const CARRY_IMAGE_MARKER = "[沿用上文图片]";

/** 用户消息展示：去掉 OCR 等内部标记，只保留用户输入文字 */
export function stripOcrForDisplay(content: string): string {
  if (!content) return "";
  let text = content;
  for (const marker of [IMAGE_OCR_MARKER, CARRY_IMAGE_MARKER]) {
    if (text.includes(marker)) {
      text = text.split(marker, 1)[0];
    }
  }
  return text.trim();
}

export function userMessageDisplayText(
  content: string,
  displayContent?: string | null
): string {
  if (displayContent != null && displayContent !== "") {
    return displayContent;
  }
  return stripOcrForDisplay(content);
}

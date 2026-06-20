/** 管理后台权限：通过环境变量配置管理员邮箱列表 */

import { shouldSkipAuthInDev } from "@/lib/auth/dev-auth";

export function getAdminEmails(): string[] {
  const raw =
    process.env.ADMIN_EMAILS?.trim() ||
    process.env.NEXT_PUBLIC_ADMIN_EMAILS?.trim() ||
    "";
  if (!raw) return [];
  return raw
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

/** 是否已配置管理员白名单 */
export function hasAdminAllowlist(): boolean {
  return getAdminEmails().length > 0;
}

export function isAdminEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  const admins = getAdminEmails();
  if (admins.length === 0) {
    // 未配白名单：仅允许显式跳过鉴权的纯本地开发
    return shouldSkipAuthInDev();
  }
  return admins.includes(email.trim().toLowerCase());
}

export function getEmailFromClaims(
  claims: Record<string, unknown> | null | undefined
): string | null {
  if (!claims) return null;
  const email = claims.email;
  if (typeof email === "string" && email) return email;
  return null;
}

/**
 * 只允许站内相对路径，防止开放重定向攻击
 */
export function safeNextPath(raw: string | null | undefined, fallback = "/") {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) {
    return fallback;
  }

  return raw;
}

export const loginErrorMessages: Record<string, string> = {
  auth_callback_failed: "登录验证失败，请重新登录。",
  config_missing: "服务配置异常，请联系管理员。",
};

export function getLoginErrorMessage(code: string | null) {
  if (!code) return null;
  return loginErrorMessages[code] ?? "登录过程中出现错误，请重试。";
}

import { NextResponse } from "next/server";

/**
 * 向浏览器暴露 API 基址。
 * 仅返回 NEXT_PUBLIC_API_URL；未配置时返回空字符串，浏览器走同源 /api/* rewrite。
 * BACKEND_URL 仅供 Next.js 服务端代理，不要下发给浏览器。
 */
export async function GET() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL?.trim() || "";

  return NextResponse.json({
    apiBaseUrl: apiBaseUrl.replace(/\/$/, ""),
  });
}

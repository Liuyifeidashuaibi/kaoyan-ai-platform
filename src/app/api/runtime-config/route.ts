import { NextResponse } from "next/server";

/** 向浏览器暴露后端公网地址（读服务端环境变量，无需 rebuild） */
export async function GET() {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.BACKEND_URL?.trim() ||
    "";

  return NextResponse.json({
    apiBaseUrl: apiBaseUrl.replace(/\/$/, ""),
  });
}

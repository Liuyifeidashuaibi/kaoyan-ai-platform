import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL?.trim() || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Docker 生产镜像使用 standalone 输出
  output: process.env.DOCKER_BUILD === "1" ? "standalone" : undefined,
  webpack(config) {
    // 默认使用系统 CPU 核心数，仅内存紧张时降低
    // config.parallelism 不设置则使用 Node.js 默认值 (os.availableParallelism)
    return config;
  },
  experimental: {
    // 错题本/聊天上传经 Next rewrite 代理，默认 10MB 会截断大文件
    proxyClientMaxBodySize: "100mb",
    // 翻译（尤其图片 OCR、视频）可能超过默认 30s 代理超时
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/chat/:path*",
        destination: `${backendUrl}/api/chat/:path*`,
      },
      {
        source: "/api/wrong-questions/:path*",
        destination: `${backendUrl}/api/wrong-questions/:path*`,
      },
      {
        source: "/api/settings",
        destination: `${backendUrl}/api/settings`,
      },
      {
        source: "/api/settings/:path*",
        destination: `${backendUrl}/api/settings/:path*`,
      },
      {
        source: "/api/translator/:path*",
        destination: `${backendUrl}/api/translator/:path*`,
      },
      {
        source: "/api/en-learn/:path*",
        destination: `${backendUrl}/api/en-learn/:path*`,
      },
      {
        source: "/api/word-query",
        destination: `${backendUrl}/api/word-query`,
      },
      {
        source: "/api/tts/:path*",
        destination: `${backendUrl}/api/tts/:path*`,
      },
      {
        source: "/api/community/:path*",
        destination: `${backendUrl}/api/community/:path*`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${backendUrl}/api/admin/:path*`,
      },
      {
        source: "/api/tasks/:path*",
        destination: `${backendUrl}/api/tasks/:path*`,
      },
      {
        source: "/api/backend-health",
        destination: `${backendUrl}/api/health`,
      },
      {
        source: "/api/debug/:path*",
        destination: `${backendUrl}/api/debug/:path*`,
      },
      {
        source: "/uploads/:path*",
        destination: `${backendUrl}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;

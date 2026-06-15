import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL?.trim() || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  webpack(config) {
    // Reduce parallel workers so compilation doesn't exhaust system memory.
    config.parallelism = 1;
    return config;
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
        source: "/api/community/:path*",
        destination: `${backendUrl}/api/community/:path*`,
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

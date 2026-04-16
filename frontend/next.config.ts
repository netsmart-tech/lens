import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const internal =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8100";
    return [
      {
        source: "/api/:path*",
        destination: `${internal}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

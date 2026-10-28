import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.TOLLGATE_API_URL || "http://127.0.0.1:8187"}/:path*`,
      },
    ];
  },
  poweredByHeader: false,
  devIndicators: false,
};
export default config;

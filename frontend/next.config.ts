import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  async redirects() {
    return [
      { source: "/prompt-presets", destination: "/settings?tab=prompt-override", permanent: false },
      {
        source: "/settings",
        has: [{ type: "query", key: "tab", value: "prompt-presets" }],
        destination: "/settings?tab=prompt-override",
        permanent: false,
      },
      {
        source: "/settings",
        has: [{ type: "query", key: "tab", value: "providers" }],
        destination: "/settings?tab=general",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;

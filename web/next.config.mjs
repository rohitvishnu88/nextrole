/** @type {import('next').NextConfig} */
const config = {
  experimental: {
    // Resume parsing and section drafts are synchronous Claude calls that can take ~60s;
    // the rewrite proxy's default 30s timeout would fail them while the server still works.
    proxyTimeout: 180_000,
  },
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default config;

import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname
  },
  async rewrites() {
    const apiBase = process.env.MANIMIND_API_BASE_URL ?? 'http://127.0.0.1:8000';
    return [
      {
        source: '/outputs/:path*',
        destination: `${apiBase}/outputs/:path*`
      }
    ];
  }
};

export default nextConfig;

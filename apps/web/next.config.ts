import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    return [{ source: '/favicon.ico', destination: '/icon.svg' }]
  },
}

export default nextConfig

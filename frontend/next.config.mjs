/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === 'production';

const nextConfig = {
  reactStrictMode: true,
  // Enable standalone output for Docker production builds
  output: isProd ? 'standalone' : undefined,
  experimental: {
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
  // No remote image hosts needed — only local /logo.png is used
  images: { remotePatterns: [] },
  // Security headers (M-5, M-6, M-6)
  async headers() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; " +
              "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; " +
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
              "img-src 'self' https: data: blob:; " +
              "font-src 'self' data: https://fonts.gstatic.com; " +
              `connect-src 'self' ${apiUrl.replace('/api', '')} https://*.supabase.co wss://*.supabase.co https://www.google-analytics.com https://region1.google-analytics.com https://analytics.google.com; ` +
              "frame-ancestors 'none'; " +
              "base-uri 'self'; " +
              "form-action 'self'; " +
              "object-src 'none'",
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;

import type { NextConfig } from "next";
import withBundleAnalyzer from "@next/bundle-analyzer";

const withAnalyzer = withBundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
  output: "standalone",     // Optimized Docker image
  reactStrictMode: true,
  swcMinify: true,

  // Environment variables exposed to the client
  env: {
    NEXT_PUBLIC_APP_NAME: "ResQAI",
    NEXT_PUBLIC_APP_VERSION: process.env.APP_VERSION ?? "1.0.0",
  },

  // Image optimization
  images: {
    domains: [
      "res.cloudinary.com",
      "lh3.googleusercontent.com",
      "maps.googleapis.com",
    ],
    formats: ["image/avif", "image/webp"],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    minimumCacheTTL: 3600,
  },

  // Experimental features
  experimental: {
    serverActions: { allowedOrigins: ["localhost:3000"] },
    optimizePackageImports: [
      "lucide-react",
      "framer-motion",
      "@radix-ui/react-icons",
      "recharts",
    ],
    typedRoutes: true,
  },

  // Security headers
  headers: async () => [
    {
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-XSS-Protection", value: "1; mode=block" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        {
          key: "Permissions-Policy",
          value: "camera=(), microphone=(), geolocation=(self)",
        },
      ],
    },
  ],

  // Webpack customizations
  webpack: (config, { isServer }) => {
    // Ignore mapbox-gl server-side
    if (isServer) {
      config.externals = [...(config.externals || []), "mapbox-gl"];
    }
    return config;
  },

  // Redirect rules
  redirects: async () => [
    {
      source: "/login",
      destination: "/(auth)/login",
      permanent: false,
    },
  ],
};

export default withAnalyzer(nextConfig);

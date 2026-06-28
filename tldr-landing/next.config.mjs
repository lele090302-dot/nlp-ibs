/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "picsum.photos" },
    ],
  },
  // Prevent Next.js from bundling native addons — they must be loaded at runtime
  serverExternalPackages: ["better-sqlite3"],
};

export default nextConfig;

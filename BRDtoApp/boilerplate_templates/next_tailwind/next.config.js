/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  devIndicators: {
    autoHide: true,
  },
  images: {
    unoptimized: true,
  },
  serverRuntimeConfig: {
    port: 3003
  }
}

export default nextConfig

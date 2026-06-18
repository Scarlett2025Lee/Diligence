/**
 * Proxies /api/* to the FastAPI backend so the browser sees a same-origin
 * fetch (no CORS) and the React code stays portable across local dev and
 * any future deployment behind a single domain.
 *
 * Configure via NEXT_PUBLIC_BACKEND_URL or fall back to localhost:8000.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;

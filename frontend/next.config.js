/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  trailingSlash: false,
  webpack: (config) => {
    config.externals.push({
      'utf-8-validate': 'commonjs utf-8-validate',
      'bufferutil': 'commonjs bufferutil',
    })
    return config
  },
  env: {
    NEXT_PUBLIC_API_BASE: 'https://66fb-77-91-101-132.ngrok-free.app'
  },
  // Add API proxy configuration
  async rewrites() {
    return [
      // Single, robust generic proxy rule.
      // Next.js `trailingSlash: true` should handle normalizing incoming paths.
      // The :path* should capture everything including query params.
      // The destination should also use :path*/ to ensure the trailing slash is passed to FastAPI.
      {
        source: '/api/:path*', // CHANGED: Removed trailing slash from source pattern
        destination: 'http://localhost:8000/:path*/', // Destination still ensures trailing slash for FastAPI
      }
    ];
  },
  // Отключаем строгую проверку HTTPS для разработки
  devIndicators: {
    buildActivity: true,
  },
  // Обрабатываем ошибки CORS и SSL
  onDemandEntries: {
    // период в мс, в течение которого страница должна быть сохранена в буфере
    maxInactiveAge: 25 * 1000,
    // количество страниц, которые должны быть сохранены в буфере
    pagesBufferLength: 2,
  }
}

module.exports = nextConfig; 
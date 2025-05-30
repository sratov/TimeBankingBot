/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  trailingSlash: true,
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
      {
        source: '/api/auth/telegram',
        destination: 'http://localhost:8000/auth/telegram',
      },
      {
        source: '/api/debug/auth',
        destination: 'http://localhost:8000/debug/auth',
      },
      {
        source: '/api/listings/', // For the working case
        destination: 'http://localhost:8000/listings/',
      },
      // Fallback generic rules (can be kept or commented out for testing)
      {
        source: '/api/:path*/', 
        destination: 'http://localhost:8000/:path*/',
      },
      {
        source: '/api/:path*', 
        destination: 'http://localhost:8000/:path*',
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
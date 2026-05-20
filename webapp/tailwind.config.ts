import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"PingFang SC"', '"Helvetica Neue"', 'sans-serif'],
        serif: ['"Noto Serif SC"', '"Songti SC"', 'serif']
      },
      colors: {
        bg: '#fbfbfd',
        ink: '#1d1d1f',
        ink2: '#6e6e73',
        line: '#d2d2d7',
        accent: '#0071e3'
      },
      animation: {
        shimmer: 'shimmer 2.4s linear infinite',
        pulse: 'pulse 1.6s ease-in-out infinite'
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' }
        }
      }
    }
  },
  plugins: []
};
export default config;

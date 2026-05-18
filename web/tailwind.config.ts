import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#faf7f2',
          100: '#f3ece0',
          200: '#e6d9be',
          300: '#d3bd92',
          400: '#bf9d68',
          500: '#a8814a',
          600: '#8a6638',
          700: '#6b4d2c',
          800: '#4a3520',
          900: '#2a1e13',
          950: '#161009',
        },
        cinnabar: {
          50: '#fbf4f1',
          100: '#f7e5dc',
          200: '#efc8b6',
          300: '#e3a487',
          400: '#d57b58',
          500: '#c45b3b',
          600: '#a8442c',
          700: '#823322',
          800: '#5d2218',
          900: '#3d160f',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        serif: ['var(--font-serif)', 'Noto Serif SC', 'SimSun', 'serif'],
      },
      boxShadow: {
        ink: '0 10px 40px -10px rgba(58, 38, 19, 0.25)',
      },
      backgroundImage: {
        'paper': "radial-gradient(at 30% 20%, rgba(212, 173, 119, 0.18) 0px, transparent 50%), radial-gradient(at 80% 80%, rgba(168, 65, 44, 0.10) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
};

export default config;

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: { navy: { 900: '#0b2545', 800: '#13315c', 700: '#1d4073', 100: '#e3ebf6', 50: '#f3f6fb' } },
    },
  },
  plugins: [],
}

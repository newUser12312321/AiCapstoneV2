/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        pass: '#22c55e',   // 합격 녹색
        fail: '#ef4444',   // 불합격 빨강
      },
    },
  },
  plugins: [],
}

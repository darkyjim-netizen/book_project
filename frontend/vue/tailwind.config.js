/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Pretendard', 'Noto Sans KR', 'sans-serif'] }
    }
  },
  plugins: []
}
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        gold: {
          light: '#e8c97a',
          DEFAULT: '#c9a96e',
          dark: '#8b6f3a',
        },
        navy: {
          light: '#1a1a2e',
          DEFAULT: '#0d0d1a',
          dark: '#05050a',
        }
      },
      fontFamily: {
        sans: ['"DM Sans"', 'sans-serif'],
        serif: ['"Playfair Display"', 'serif'],
      },
    },
  },
  plugins: [],
}
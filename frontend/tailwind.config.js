/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        finance: {
          dark: '#0a192f',
          card: '#112240',
          accent: '#f1c40f',
          success: '#2ecc71',
          danger: '#e74c3c',
          text: '#f8f9fa',
          textMuted: '#8892b0'
        }
      }
    },
  },
  plugins: [],
}

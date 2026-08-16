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
          dark: '#f8fafc',
          card: '#ffffff',
          accent: '#d97706',
          success: '#10b981',
          danger: '#ef4444',
          text: '#0f172a',
          textMuted: '#64748b'
        }
      }
    },
  },
  plugins: [],
}

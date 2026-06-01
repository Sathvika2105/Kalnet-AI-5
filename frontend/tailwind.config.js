/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        sidebar: {
          bg: '#0f172a',
          hover: '#1e293b',
          active: '#3b82f6',
        },
        card: {
          bg: '#1e293b',
          border: '#334155',
        }
      }
    },
  },
  plugins: [],
}

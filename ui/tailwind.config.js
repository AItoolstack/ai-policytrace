/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark:  '#1F2937',
          blue:  '#2563EB',
          teal:  '#008080',
          50:    '#f0fdfc',
          100:   '#ccfbf1',
          600:   '#2563EB',
          700:   '#1d4ed8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

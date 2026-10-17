/** @type {import('tailwindcss').Config} */
// ai·toolstack design tokens (mirrors the ai-toolstack.com theme)
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: '#121826', // midnight slate ground
          900: '#121826',
          800: '#182033',     // surface
          700: '#1F2940',     // raised
          600: '#2C3752',     // rule
          500: '#3A4766',
          400: '#7E88A2',     // dim text (AA on ink)
          300: '#9CA6BA',     // muted text
          200: '#CDD3DE',     // body text on ink
          100: '#ECEAE4',     // bone
        },
        paper: {
          DEFAULT: '#F6F5F1',
          sheet: '#FFFFFF',
          rule: '#E2E0D9',
          muted: '#5A6478',
          ink: '#2B3245',
        },
        signal: {
          DEFAULT: '#E0A946', // amber accent
          hover: '#ECBE6A',
          deep: '#8F5A0E',    // amber for text on paper (AA)
          tint: '#FBF3E4',
        },
        state: {
          pass: '#1F7A4D',
          'pass-tint': '#EDF6F0',
          override: '#3B4A6B',
          'override-tint': '#EEF1F6',
          flag: '#B4532A',
          'flag-tint': '#F8EDE7',
        },
      },
      fontFamily: {
        sans: ['Geist', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        sheet: '0 1px 0 rgba(18,24,38,0.04), 0 8px 24px -16px rgba(18,24,38,0.25)',
        page: '0 24px 60px -30px rgba(0,0,0,0.65)',
      },
    },
  },
  plugins: [],
}

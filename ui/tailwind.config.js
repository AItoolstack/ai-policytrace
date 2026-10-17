/** @type {import('tailwindcss').Config} */
// ai·toolstack design tokens (mirrors the ai-toolstack.com light theme)
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          // Light scheme matching ai-toolstack.com 2.5. Names kept so classes still read
          // "ground → surface → raised → rule → text"; values run light to dark.
          DEFAULT: '#FFFFFF', // page ground
          900: '#FFFFFF',
          800: '#FAFAF8',     // surface (bars, cards)
          700: '#ECEAE5',     // raised / rule
          600: '#E2E0DA',     // stronger rule
          500: '#D9D6CF',
          400: '#7A8190',     // dim text
          300: '#5B6270',     // muted text
          200: '#4A5160',     // body text
          100: '#1A1D24',     // ink
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
        page: '0 1px 2px rgba(26,29,36,0.06), 0 12px 32px -18px rgba(26,29,36,0.28)',
      },
    },
  },
  plugins: [],
}

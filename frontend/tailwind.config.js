/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', 'Fira Code', 'monospace'],
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
      },
      colors: {
        surface: {
          DEFAULT: '#0b0f1a',
          50: '#111827',
          100: '#141b2d',
          200: '#1a2238',
          300: '#1f2a44',
          400: '#263352',
        },
        accent: {
          cyan: '#00e5ff',
          green: '#00ff9d',
          amber: '#ffb300',
          red: '#ff3d57',
          purple: '#b388ff',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease forwards',
        'slide-up': 'slideUp 0.35s ease forwards',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'blink': 'blink 1s step-end infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'scan': 'scan 2s linear infinite',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
        slideUp: { '0%': { opacity: 0, transform: 'translateY(14px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        glow: { '0%': { boxShadow: '0 0 5px rgba(0,229,255,0.2)' }, '100%': { boxShadow: '0 0 20px rgba(0,229,255,0.6)' } },
        blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
        scan: { '0%': { top: '-10%' }, '100%': { top: '110%' } },
      },
    },
  },
  plugins: [],
}

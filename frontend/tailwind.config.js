/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Industrial Instrument Basalt Darks
        studio: {
          950: '#0b0c0f',
          900: '#13151b',
          850: '#1a1d25',
          800: '#242834',
          700: '#343a4a',
        },
        // Industrial Hardware Accents
        broadcast: {
          accent: '#e05338',   // Signal Orange
          live: '#e05338',     // Muted Terracotta Red
          host: '#4f78a8',     // Anodized Steel Blue
          analyst: '#876ea8',  // Anodized Slate Purple
        },
        chess: {
          blunder: '#dc2626',
          mistake: '#ea580c',
          inaccuracy: '#ca8a04',
          good: '#2563eb',
          best: '#16a34a',
          brilliant: '#0284c7',
          book: '#9333ea',
        },
      },
    },
  },
  plugins: [],
};
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Deep, neutral broadcast darks (replacing harsh blue-black)
        studio: {
          950: '#0c0d10',
          900: '#14161b',
          850: '#1c1f26',
          800: '#262a34',
          700: '#383e4d',
        },
        // Subtle, elegant tournament accents (replacing neon cyan/bright green)
        broadcast: {
          accent: '#d4af37',   // Muted tournament gold
          live: '#e05252',     // Classic broadcast red
          host: '#3b82f6',     // Slate blue
          analyst: '#8b5cf6',  // Subdued violet
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
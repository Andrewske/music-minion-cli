/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './hooks/**/*.{ts,tsx}',
  ],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        background: '#121212',
        surface: '#1E1E1E',
        primary: '#7C4DFF',
        'text-primary': '#E0E0E0',
        'text-secondary': '#9E9E9E',
        error: '#CF6679',
        success: '#4CAF50',
      },
    },
  },
  plugins: [],
};

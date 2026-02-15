/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Dark Academia
        'cormorant': ['Cormorant Garamond', 'Georgia', 'serif'],
        'crimson': ['Crimson Text', 'Georgia', 'serif'],
        // Obsidian Minimal
        'inter': ['Inter', 'system-ui', 'sans-serif'],
        'sf-mono': ['SF Mono', 'Menlo', 'monospace'],
        // Slate & Copper
        'dm-sans': ['DM Sans', 'system-ui', 'sans-serif'],
        // Midnight Violet
        'source-sans': ['Source Sans 3', 'system-ui', 'sans-serif'],
        // Carbon Monochrome
        'geist': ['Geist', 'system-ui', 'sans-serif'],
        'jetbrains': ['JetBrains Mono', 'monospace'],
      },
      colors: {
        // Dark Academia palette
        academia: {
          bg: '#1a1612',
          surface: '#2a2420',
          burgundy: '#722F37',
          forest: '#2D4A3E',
          cream: '#F5F0E6',
          gold: '#B8860B',
          parchment: '#E8DCC4',
        },
        // Obsidian palette
        obsidian: {
          black: '#000000',
          surface: '#0a0a0a',
          border: '#1a1a1a',
          accent: '#1DB954',
        },
        // Slate & Copper palette
        copper: {
          bg: '#18181B',
          surface: '#27272A',
          accent: '#C77B4A',
          highlight: '#E8A87C',
        },
        // Midnight Violet palette
        midnight: {
          bg: '#0F172A',
          surface: '#1E293B',
          violet: '#8B5CF6',
          muted: '#6366F1',
        },
        // Carbon palette
        carbon: {
          black: '#0C0C0C',
          surface: '#171717',
          border: '#262626',
          teal: '#14B8A6',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 5px currentColor' },
          '50%': { boxShadow: '0 0 15px currentColor' },
        },
      },
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
}


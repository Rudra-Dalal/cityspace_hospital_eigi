/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        clinic: {
          50: '#f0f9fa',
          100: '#d9f1f3',
          200: '#b7e3e8',
          300: '#85ced7',
          400: '#4fafbd',
          500: '#3493a3',
          600: '#2e7789',
          700: '#2b6170',
          800: '#2a505d',
          900: '#274450',
        },
      },
      fontFamily: {
        sans: ['"Source Sans 3"', 'Segoe UI', 'system-ui', 'sans-serif'],
        display: ['"Fraunces"', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}

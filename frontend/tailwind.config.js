/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Make the `font-sans` utility resolve to Outfit (the font loaded in index.html and
      // set on <body>). Without this, Layout's `font-sans` class overrode the body font
      // with the default system stack everywhere except the dashboard overlay.
      fontFamily: {
        sans: ['Outfit', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Oxygen', 'Ubuntu', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

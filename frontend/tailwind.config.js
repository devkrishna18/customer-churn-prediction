/** @type {import('tailwindcss').Config} */
export default {
  // This is the most important part.
  // It tells Tailwind to scan all your .js, .ts, .jsx, and .tsx files inside the 'src' folder.
  content: [
    "./src/**/*.{js,ts,jsx,tsx}",
    "./index.html"
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

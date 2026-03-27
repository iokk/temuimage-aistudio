import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f5fbff",
          100: "#e6f4ff",
          500: "#0369a1",
          900: "#0f172a",
        },
      },
    },
  },
  plugins: [],
}

export default config

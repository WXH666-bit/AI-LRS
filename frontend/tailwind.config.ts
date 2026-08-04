import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        night: {
          950: "#0b0f1c",
          900: "#111827",
          800: "#1a2332",
          700: "#263245",
          600: "#34415a",
        },
        moon: "#e8e6e1",
        blood: "#c0392b",
        wolf: "#8e44ad",
      },
    },
  },
  plugins: [],
} satisfies Config;

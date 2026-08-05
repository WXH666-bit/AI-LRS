import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b1018",
          900: "#111925",
          800: "#151e2d",
          700: "#1c2738",
          600: "#2b3a4e",
        },
        bone: "#f3eee5",
        smoke: "#91a0b5",
        gold: "#c89b3c",
        cinnabar: "#d9574f",
        sage: "#6fb3a5",
        night: {
          950: "#0b1018",
          900: "#111925",
          800: "#151e2d",
          700: "#1c2738",
          600: "#2b3a4e",
        },
        moon: "#f3eee5",
        blood: "#d9574f",
        wolf: "#9b78c5",
      },
    },
  },
  plugins: [],
} satisfies Config;

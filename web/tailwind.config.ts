import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream:          "#F7F5F0",
        accent:         "#E07A3C",
        "accent-hover": "#C96A2E",
        "accent-light": "#FEF3E8",
        navy:           "#1A1714",
        surface:        "#FFFFFF",
        "warm-border":  "#E8E3D9",
        muted:          "#6B655C",
        "green-soft":   "#E8F5EE",
        "green-text":   "#2D7A4F",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.25rem",
      },
      fontFamily: {
        sans:  ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
        brand: ["var(--font-brand)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

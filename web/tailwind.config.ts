import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper:       "#F5F4F0",
        surface:     "#FFFFFF",
        ink:         "#000000",
        "ink-muted": "#5A5A57",
        rule:        "#000000",
        "rule-soft": "#D9D7D0",
        blue:        "#378ADD",
        yellow:      "#EF9F27",
        red:         "#E24B4A",
      },
      fontFamily: {
        sans: ["var(--font-jost)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

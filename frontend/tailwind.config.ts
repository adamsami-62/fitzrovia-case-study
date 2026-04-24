import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper:  "#faf8f4",
        ink:    "#1a1a1a",
        navy:   "#1a2540",
        rust:   "#c8553d",
        rule:   "#e5e1d8",
        muted:  "#6b6b6b",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans:    ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-xl": ["3.5rem",  { lineHeight: "1.05", letterSpacing: "-0.02em" }],
        "display-lg": ["2.25rem", { lineHeight: "1.1",  letterSpacing: "-0.015em" }],
      },
    },
  },
  plugins: [],
};
export default config;

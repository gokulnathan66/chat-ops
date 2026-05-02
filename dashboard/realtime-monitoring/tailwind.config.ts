import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        surface: "#fafaf8",
      },
      boxShadow: {
        card:         "0 1px 4px 0 rgb(0 0 0 / .05), 0 1px 2px -1px rgb(0 0 0 / .04)",
        "card-md":    "0 4px 16px -2px rgb(0 0 0 / .07), 0 2px 6px -2px rgb(0 0 0 / .05)",
        "card-hover": "0 12px 36px -8px rgb(0 0 0 / .14), 0 4px 10px -4px rgb(0 0 0 / .07)",
        "nav-active": "0 1px 3px 0 rgb(0 0 0 / .25), inset 0 1px 0 rgb(255 255 255 / .1)",
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "DM Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "24px",
      },
      animation: {
        "fade-in":  "fadeIn .18s ease-out",
        "slide-up": "slideUp .22s ease-out",
      },
      keyframes: {
        fadeIn:  { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
};
export default config;

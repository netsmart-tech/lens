// Tailwind 4 autodetects content; this file exists mainly for dark-mode config
// and as a stable hook point. Tailwind 4 reads theme from CSS via @theme in globals.css.
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
};

export default config;

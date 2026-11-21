import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          950: "#070b14",
          900: "#0d1322",
          800: "#141d31",
          700: "#1c2842",
        },
        gold: {
          400: "#e2c078",
          500: "#c89b3c",
        },
      },
    },
  },
  plugins: [],
};

export default config;

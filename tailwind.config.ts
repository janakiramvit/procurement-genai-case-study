import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        novartis: {
          blue: "#0460A9",
          darkblue: "#04378A",
        },
      },
    },
  },
  plugins: [],
};
export default config;

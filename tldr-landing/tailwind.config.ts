import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        terracotta: "#C83A2A",
        burnt:      "#E7A33C",
        blush:      "#F8ECE8",
        cream:      "#FFF8F3",
        charcoal:   "#1E1B18",
        muted:      "#7A6F68",
        border:     "#EAD9D3",
      },
      fontFamily: {
        serif: ["Playfair Display", "Georgia", "serif"],
        sans:  ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        editorial: "0 2px 20px rgba(30,27,24,0.07)",
        card:      "0 1px 8px rgba(30,27,24,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;

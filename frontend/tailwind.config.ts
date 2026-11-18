import type { Config } from "tailwindcss";

const opacities: Record<string, string> = Object.fromEntries(
  Array.from({ length: 101 }, (_, index) => [String(index), String(index / 100)]),
);

export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#131620",
          900: "#1e1f24",
          800: "#2d3039",
          700: "#444752",
          600: "#5e6270",
          500: "#717686",
          400: "#8e93a4",
          300: "#b2b7c6",
          200: "#cfd4e0",
        },
        canvas: "#f6f8fc",
        surface: "#ffffff",
        accent: {
          50: "#eef4ff",
          100: "#dce8fe",
          200: "#bfd3fe",
          300: "#91b4fd",
          400: "#6090fa",
          500: "#4285f4",
          600: "#6b66e8",
          700: "#5348c7",
        },
        gemini: {
          blue: "#4285f4",
          indigo: "#7b61ff",
          violet: "#9b72cb",
          rose: "#d96570",
          surface: "#f0f4f9",
        },
      },
      fontFamily: {
        sans: [
          "Google Sans",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "Segoe UI",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "SF Mono",
          "SFMono-Regular",
          "Cascadia Code",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        float: "0 10px 36px -8px rgba(66, 133, 244, 0.12), 0 4px 18px -4px rgba(155, 114, 203, 0.08)",
        composer: "0 16px 48px -12px rgba(66, 133, 244, 0.16), 0 8px 28px -8px rgba(155, 114, 203, 0.12)",
        soft: "0 2px 14px -2px rgba(66, 133, 244, 0.06), 0 1px 4px rgba(15, 23, 42, 0.03)",
        card: "0 4px 20px -4px rgba(66, 133, 244, 0.08), 0 2px 8px -2px rgba(155, 114, 203, 0.05)",
        elevated: "0 16px 44px -10px rgba(66, 133, 244, 0.16), 0 6px 20px -6px rgba(217, 101, 112, 0.1)",
        "apple-btn": "0 6px 20px -4px rgba(123, 97, 255, 0.36)",
        "gemini-glow": "0 0 28px -4px rgba(66, 133, 244, 0.28), 0 0 44px -8px rgba(155, 114, 203, 0.24)",
      },
      borderRadius: {
        "4xl": "2rem",
      },
      opacity: opacities,
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(.98)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 50%" },
          "100%": { backgroundPosition: "-200% 50%" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.25" },
        },
        "aurora-drift": {
          "0%, 100%": { transform: "translate3d(0, 0, 0) scale(1)" },
          "33%": { transform: "translate3d(24px, -16px, 0) scale(1.06)" },
          "66%": { transform: "translate3d(-18px, 14px, 0) scale(0.96)" },
        },
      },
      animation: {
        "fade-up": "fade-up .4s cubic-bezier(.16,1,.3,1) both",
        "fade-in": "fade-in .25s ease both",
        "scale-in": "scale-in .2s cubic-bezier(.16,1,.3,1) both",
        shimmer: "shimmer 6s ease-in-out infinite",
        blink: "blink 1.1s ease-in-out infinite",
        "aurora-drift": "aurora-drift 14s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

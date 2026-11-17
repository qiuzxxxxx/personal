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
          950: "#1d1d1f",
          900: "#1d1d1f",
          800: "#333336",
          700: "#48484a",
          600: "#636366",
          500: "#6e6e73",
          400: "#86868b",
          300: "#aeaeb2",
          200: "#c7c7cc",
        },
        canvas: "#f5f5f7",
        surface: "#ffffff",
        accent: {
          50: "#e8f2ff",
          100: "#d0e5ff",
          200: "#a8ceff",
          300: "#6aadff",
          400: "#2997ff",
          500: "#0071e3",
          600: "#0077ed",
          700: "#005bb5",
        },
        /* Keep old accent-400/500/600 mapping stable for existing classes */
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "Inter",
          "Segoe UI",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: [
          "SF Mono",
          "JetBrains Mono",
          "SFMono-Regular",
          "Cascadia Code",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        float: "0 4px 24px rgba(0, 0, 0, 0.08)",
        composer: "0 8px 40px rgba(0, 0, 0, 0.12)",
        soft: "0 2px 12px rgba(0, 0, 0, 0.04)",
        card: "0 1px 3px rgba(0, 0, 0, 0.04), 0 6px 16px rgba(0, 0, 0, 0.04)",
        elevated: "0 4px 30px rgba(0, 0, 0, 0.08)",
        "apple-btn": "0 1px 3px rgba(0, 0, 0, 0.08)",
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
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.25" },
        },
      },
      animation: {
        "fade-up": "fade-up .4s cubic-bezier(.16,1,.3,1) both",
        "fade-in": "fade-in .25s ease both",
        "scale-in": "scale-in .2s cubic-bezier(.16,1,.3,1) both",
        shimmer: "shimmer 3s linear infinite",
        blink: "blink 1.1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

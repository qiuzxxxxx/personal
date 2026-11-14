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
          950: "#0b1220",
          900: "#111827",
          800: "#1f2937",
          700: "#374151",
          600: "#4b5563",
          500: "#6b7280",
          400: "#9ca3af",
          300: "#d1d5db",
        },
        canvas: "#f7f8fa",
        accent: {
          50: "#eef4ff",
          100: "#dfeaff",
          200: "#c4d8ff",
          300: "#9bbdff",
          400: "#6c98ff",
          500: "#4473f6",
          600: "#3057df",
          700: "#2846b8",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "SF Pro Display",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "SFMono-Regular",
          "Cascadia Code",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        float: "0 18px 50px -24px rgba(15, 23, 42, 0.22)",
        composer: "0 24px 65px -30px rgba(15, 23, 42, 0.35)",
        soft: "0 8px 30px -18px rgba(15, 23, 42, 0.2)",
      },
      borderRadius: {
        "4xl": "2rem",
      },
      opacity: opacities,
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(.97)" },
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
        "fade-up": "fade-up .45s cubic-bezier(.22,1,.36,1) both",
        "fade-in": "fade-in .3s ease both",
        "scale-in": "scale-in .25s cubic-bezier(.22,1,.36,1) both",
        shimmer: "shimmer 3s linear infinite",
        blink: "blink 1.1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}"],
  theme: {
    extend: {
      colors: {
        background: "#ffffff",
        foreground: "#111827",
        muted: "#6b7280",
        border: "#e5e7eb",
        accent: {
          DEFAULT: "#F97316",
          hover: "#EA580C",
          light: "#FFF7ED",
        },
        surface: "#F9FAFB",
        positive: "#16a34a",
        negative: "#dc2626",
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        display: ['"DM Sans"', '"Inter"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', '"SF Mono"', "monospace"],
      },
    },
  },
  plugins: [],
};

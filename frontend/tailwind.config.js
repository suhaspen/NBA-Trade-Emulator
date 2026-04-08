/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        canvas: "#07080c",
        surface: "#0f1118",
        surface2: "#141824",
        elevated: "#1a1f2e",
        ink: "#e8ecf4",
        ink2: "#c4cad8",
        muted: "#8b93a7",
        line: "#2a3145",
        accent: "#38bdf8",
        accentdim: "#0ea5e9",
        accentsoft: "rgba(56, 189, 248, 0.12)",
        sideb: "#818cf8",
        sidebsoft: "rgba(129, 140, 248, 0.14)",
        glow: "rgba(56, 189, 248, 0.35)",
      },
      boxShadow: {
        card: "0 0 0 1px rgba(255,255,255,0.06), 0 8px 32px rgba(0,0,0,0.45)",
        lift: "0 0 0 1px rgba(255,255,255,0.08), 0 24px 48px rgba(0,0,0,0.55)",
        inset: "inset 0 1px 0 0 rgba(255,255,255,0.06)",
      },
      backgroundImage: {
        "hero-shine":
          "linear-gradient(105deg, rgba(56,189,248,0.15) 0%, transparent 45%, rgba(129,140,248,0.08) 100%)",
      },
    },
  },
  plugins: [],
};

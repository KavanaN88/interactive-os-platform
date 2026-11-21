/** Palette from the project spec. Change colours here to re-theme the whole app. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#07111D", side: "#0B1522", card: "#111D2A", line: "#263646",
        accent: "#38BDF8", cyan: "#22D3EE", ok: "#4ADE80", warn: "#F59E0B", err: "#F43F5E",
        ink: "#F8FAFC", mute: "#AAB6C5",
      },
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "sans-serif"], mono: ["ui-monospace", "Consolas", "monospace"] },
    },
  },
  plugins: [],
};

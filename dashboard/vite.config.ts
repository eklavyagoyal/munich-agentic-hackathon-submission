import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: ["mac-mini-m4.taildd45e5.ts.net", "mac-mini-m4"],
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5178,
    strictPort: true,
    proxy: {
      "/api": process.env.API_PROXY || "http://127.0.0.1:8120",
      "/health": process.env.API_PROXY || "http://127.0.0.1:8120",
    },
  },
});

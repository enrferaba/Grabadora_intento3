import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const API_PROXY_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/auth": { target: API_PROXY_TARGET, changeOrigin: true, secure: false },
      "/transcribe": { target: API_PROXY_TARGET, changeOrigin: true, secure: false },
      "/jobs": { target: API_PROXY_TARGET, changeOrigin: true, secure: false },
      "/transcripts": { target: API_PROXY_TARGET, changeOrigin: true, secure: false },
      "/config": { target: API_PROXY_TARGET, changeOrigin: true, secure: false },
      "/healthz": { target: API_PROXY_TARGET, changeOrigin: true, secure: false },
    },
  },
});

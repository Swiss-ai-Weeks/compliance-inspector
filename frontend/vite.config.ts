import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` on :5173 proxies /api to the FastAPI server on :8080.
// Build: emits straight into backend/static, which FastAPI serves in production.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../backend/static", emptyOutDir: true },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8080", changeOrigin: true } } },
});

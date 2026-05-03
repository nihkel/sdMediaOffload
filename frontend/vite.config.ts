import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.BACKEND_URL || process.env.BACKEND_URL || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      proxy: {
        "/api": { target: backend, changeOrigin: true, ws: true },
      },
    },
  };
});

import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    root: "apps/web",
    plugins: [react()],
    server: {
      host: env.VITE_HOST || "127.0.0.1",
      port: __WEB_PORT__,
      strictPort: true,
      // In development the browser talks to Vite, which passes /api to the server.
      proxy: { "/api": { target: env.SERVER_URL || "http://127.0.0.1:__SERVER_PORT__", changeOrigin: false } },
    },
    build: { outDir: resolve(process.cwd(), "dist/web"), emptyOutDir: true },
  };
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 开发环境把 /api 代理到后端 FastAPI（8000 端口），避免跨域问题
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});

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
  build: {
    rollupOptions: {
      output: {
        // 手动拆包：框架、UI 库、Markdown 渲染器各自成 chunk，
        // 业务代码按路由懒加载，避免单个 chunk 过大。
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          antd: ["antd", "@ant-design/icons"],
          markdown: ["react-markdown", "remark-gfm"],
        },
      },
    },
  },
});

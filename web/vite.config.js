import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期代理：前端代码一律写相对路径，跨源问题由 proxy 解决（任务书 6.1）。
// 生产构建后 dist/ 由后端 StaticFiles 同源托管，同样不需要处理 CORS。
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/news':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})

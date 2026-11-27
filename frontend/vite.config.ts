import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.PLATFORM_BACKEND_URL || 'http://127.0.0.1:5100'
  const proxy = { '/api': { target, changeOrigin: true, secure: true } }
  return { plugins: [vue()], base: env.VITE_BASE || '/', define: { 'import.meta.env.VITE_USE_BACKEND': JSON.stringify('1'), 'import.meta.env.VITE_DEMO_MODE': JSON.stringify(env.VITE_DEMO_MODE || '') }, resolve: { alias: { '@':fileURLToPath(new URL('./src/modules',import.meta.url)), 'element-plus':fileURLToPath(new URL('./src/platformUi/controls.ts',import.meta.url)), '@element-plus/icons-vue':fileURLToPath(new URL('./src/platformUi/icons.ts',import.meta.url)) } }, server: { host: '127.0.0.1', port: 5189, strictPort: true, proxy }, preview: { host: '127.0.0.1', port: 5189, strictPort: true, proxy },
    optimizeDeps: { include: ['bootstrap/js/dist/collapse', 'bootstrap/js/dist/dropdown', 'bootstrap/js/dist/modal', 'bootstrap/js/dist/offcanvas', 'bootstrap/js/dist/tooltip', 'bootstrap/js/dist/popover', 'bootstrap/js/dist/toast', 'pdfmake/build/pdfmake'] } }
})

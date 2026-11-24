import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'
export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('./src/modules', import.meta.url)) } },
  test: { include: ['src/services/platform/**/*.test.ts'], environment: 'node' },
})

import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/e2e', fullyParallel: false, workers: 2,
  globalSetup: './tests/e2e/global-setup.mjs',
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173', browserName: 'chromium', channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
})

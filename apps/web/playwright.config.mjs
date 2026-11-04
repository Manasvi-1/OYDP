import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: 'line',
  use: {
    baseURL: process.env.WEB_ORIGIN || 'http://127.0.0.1:3000',
  },
})

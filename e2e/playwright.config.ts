import { defineConfig, devices } from '@playwright/test';
import * as fs from 'fs';

// Check for ngrok URL (created by ./scripts/start-ngrok.sh)
let ngrokUrl: string | undefined;
try {
  if (fs.existsSync('/tmp/ngrok_url.txt')) {
    ngrokUrl = fs.readFileSync('/tmp/ngrok_url.txt', 'utf-8').trim();
    console.log(`ngrok URL detected: ${ngrokUrl}`);
  }
} catch {
  // ngrok not running, use localhost
}

export default defineConfig({
  testDir: './tests',
  fullyParallel: false, // Run tests sequentially for database state consistency
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Single worker to avoid database race conditions
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],

  use: {
    baseURL: 'http://localhost:4200',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // Make ngrok URL available to tests via extraHTTPHeaders or custom fixture
    extraHTTPHeaders: ngrokUrl ? { 'X-Ngrok-URL': ngrokUrl } : {},
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Run backend and frontend before tests
  // IMPORTANT: Uses port 5002 to avoid conflicts with development backend on 5001
  webServer: [
    {
      command: 'cd .. && source .venv/bin/activate && FLASK_ENV=testing python3 -c "from app import app; app.run(host=\'0.0.0.0\', port=5002, debug=False)"',
      url: 'http://localhost:5002/api/version',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: 'cd ../frontend && npm run start -- --configuration=e2e',
      url: 'http://localhost:4200',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],

  // Global setup to reset database before all tests
  globalSetup: './global-setup.ts',
});

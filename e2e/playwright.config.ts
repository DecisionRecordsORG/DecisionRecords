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
  // E2E_SERVERS_STARTED=1: the caller has started both itself (the Enterprise CI does,
  // to run the backend in Enterprise mode), so nothing is started or waited for here.
  webServer: process.env.E2E_SERVERS_STARTED ? undefined : [
    {
      // MCP_RESOURCE_URL and OAUTH_ISSUER: the addresses the Enterprise OAuth server needs
      // before it can be switched on (tests/oauth-consent.spec.ts). They change nothing else.
      // threaded=False, as the Enterprise CI starts it: the test backend keeps its data in
      // in-memory SQLite on one connection, and two requests handled at once on that one
      // connection fail now and then ("cannot commit transaction", rows that are not there).
      command: 'cd .. && source .venv/bin/activate && FLASK_ENV=testing MCP_RESOURCE_URL=http://localhost:4200/api/mcp OAUTH_ISSUER=http://localhost:4200 python3 -c "from app import app; app.run(host=\'0.0.0.0\', port=5002, debug=False, threaded=False)"',
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

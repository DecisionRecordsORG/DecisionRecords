import { request } from '@playwright/test';

const API_URL = 'http://localhost:5001';

async function globalSetup() {
  console.log('Global setup: Resetting test database...');

  const apiContext = await request.newContext({
    baseURL: API_URL,
  });

  try {
    // Reset database to clean state
    const resetResponse = await apiContext.post('/api/test/reset-database');
    if (!resetResponse.ok()) {
      console.warn('Warning: Could not reset database. Response:', await resetResponse.text());
    } else {
      console.log('Database reset successful');
    }

    // Create test users for various scenarios
    const testUsers = [
      { email: 'admin@test-org.com', password: 'TestPass123', name: 'Test Admin', role: 'admin', domain: 'test-org.com' },
      { email: 'steward@test-org.com', password: 'TestPass123', name: 'Test Steward', role: 'steward', domain: 'test-org.com' },
      { email: 'user@test-org.com', password: 'TestPass123', name: 'Test User', role: 'user', domain: 'test-org.com' },
      { email: 'provisional@new-org.com', password: 'TestPass123', name: 'Provisional Admin', role: 'provisional_admin', domain: 'new-org.com' },
    ];

    for (const user of testUsers) {
      const response = await apiContext.post('/api/test/create-user', {
        data: user,
      });
      if (!response.ok()) {
        console.warn(`Warning: Could not create user ${user.email}. Response:`, await response.text());
      } else {
        console.log(`Created test user: ${user.email} (${user.role})`);
      }
    }

    // Set tenant maturity states for governance tests
    const maturitySettings = [
      { domain: 'test-org.com', state: 'mature' },
      { domain: 'new-org.com', state: 'bootstrap' },
    ];

    for (const setting of maturitySettings) {
      const response = await apiContext.post('/api/test/set-tenant-maturity', {
        data: setting,
      });
      if (!response.ok()) {
        console.warn(`Warning: Could not set maturity for ${setting.domain}. Response:`, await response.text());
      } else {
        console.log(`Set ${setting.domain} maturity to ${setting.state}`);
      }
    }

    console.log('Global setup complete');
  } catch (error) {
    console.error('Global setup error:', error);
    // Don't fail - tests might still work with existing data
  } finally {
    await apiContext.dispose();
  }
}

export default globalSetup;

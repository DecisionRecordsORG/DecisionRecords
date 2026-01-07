import { request } from '@playwright/test';

// E2E tests use port 5002 to avoid conflicts with development backend on 5001
const API_URL = 'http://localhost:5002';

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

    // Login as admin to create test data
    console.log('Logging in as admin to create test data...');
    const loginResponse = await apiContext.post('/api/auth/login', {
      data: {
        email: 'admin@test-org.com',
        password: 'TestPass123'
      }
    });

    if (!loginResponse.ok()) {
      console.warn('Warning: Could not login as admin. Response:', await loginResponse.text());
    } else {
      console.log('Admin login successful');

      // Create additional spaces (we need at least 2 for space filter tests)
      // Note: "General" default space is created automatically
      const testSpaces = [
        { name: 'Engineering', description: 'Engineering team decisions' },
        { name: 'Product', description: 'Product team decisions' },
      ];

      const createdSpaceIds: number[] = [];

      for (const space of testSpaces) {
        const spaceResponse = await apiContext.post('/api/spaces', {
          data: space
        });
        if (!spaceResponse.ok()) {
          console.warn(`Warning: Could not create space ${space.name}. Response:`, await spaceResponse.text());
        } else {
          const spaceData = await spaceResponse.json();
          createdSpaceIds.push(spaceData.id);
          console.log(`Created test space: ${space.name} (ID: ${spaceData.id})`);
        }
      }

      // Get the General space ID for decision creation
      const spacesResponse = await apiContext.get('/api/spaces');
      let generalSpaceId: number | null = null;
      if (spacesResponse.ok()) {
        const spaces = await spacesResponse.json();
        const generalSpace = spaces.find((s: any) => s.name === 'General');
        if (generalSpace) {
          generalSpaceId = generalSpace.id;
          console.log(`Found General space: ID ${generalSpaceId}`);
        }
      }

      // Create test decisions (we need at least 2 for edit/history tests)
      const testDecisions = [
        {
          title: 'Use TypeScript for Frontend Development',
          context: 'We need to choose a language for our frontend application that provides type safety and good tooling support.',
          decision: 'We will use TypeScript for all frontend development to benefit from static typing, better IDE support, and improved code quality.',
          status: 'accepted',
          consequences: 'Team needs to learn TypeScript syntax. Build process becomes slightly more complex. Code quality and maintainability improve significantly.',
        },
        {
          title: 'Adopt Microservices Architecture',
          context: 'Our monolithic application is becoming difficult to maintain and scale. We need to evaluate our architectural approach.',
          decision: 'We will gradually migrate to a microservices architecture, starting with the most isolated modules.',
          status: 'proposed',
          consequences: 'Requires investment in DevOps infrastructure. Increases operational complexity. Enables independent scaling and deployment of services.',
        },
      ];

      for (const decision of testDecisions) {
        const decisionResponse = await apiContext.post('/api/decisions', {
          data: decision
        });
        if (!decisionResponse.ok()) {
          console.warn(`Warning: Could not create decision "${decision.title}". Response:`, await decisionResponse.text());
        } else {
          const decisionData = await decisionResponse.json();
          console.log(`Created test decision: ${decision.title} (ID: ${decisionData.id})`);

          // Associate decision with spaces if we have space IDs
          if (generalSpaceId && createdSpaceIds.length > 0) {
            const spaceIds = [generalSpaceId, createdSpaceIds[0]]; // Link to General + first custom space
            const linkResponse = await apiContext.put(`/api/decisions/${decisionData.id}/spaces`, {
              data: { space_ids: spaceIds }
            });
            if (linkResponse.ok()) {
              console.log(`  Linked decision to ${spaceIds.length} spaces`);
            }
          }
        }
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

/**
 * EE Component Stubs for Community Edition
 *
 * These stub exports allow the CE build to compile without the ee/ directory.
 * All EE components are aliased to FeatureUnavailableComponent.
 *
 * This file is used via tsconfig paths in CE builds.
 */
import { FeatureUnavailableComponent } from '../app/components/feature-unavailable/feature-unavailable.component';

// Slack components
export { FeatureUnavailableComponent as SlackInstalledComponent };
export { FeatureUnavailableComponent as SlackIntegrationComponent };
export { FeatureUnavailableComponent as SlackLinkAccountComponent };

// Teams components
export { FeatureUnavailableComponent as TeamsInstalledComponent };
export { FeatureUnavailableComponent as TeamsIntegrationComponent };
export { FeatureUnavailableComponent as TeamsLinkAccountComponent };

// AI/MCP components
export { FeatureUnavailableComponent as AiApiIntegrationComponent };
export { FeatureUnavailableComponent as McpIntegrationComponent };

// Marketing pages
export { FeatureUnavailableComponent as HomepageComponent };
export { FeatureUnavailableComponent as SolutionsComponent };
export { FeatureUnavailableComponent as LicensingComponent };
export { FeatureUnavailableComponent as LandingComponent };

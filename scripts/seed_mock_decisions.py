#!/usr/bin/env python3
"""
Seed mock architecture decisions for a tenant.

Usage:
    python scripts/seed_mock_decisions.py brandnewcorp.com
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        import re
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)(\?.*)?', database_url)
        if match:
            user, password, host, port, database, params = match.groups()
            return psycopg2.connect(
                host=host,
                port=int(port),
                database=database,
                user=user,
                password=password,
                sslmode='require'
            )

    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=int(os.environ.get('POSTGRES_PORT', 5432)),
        database=os.environ.get('POSTGRES_DB', 'postgres'),
        user=os.environ.get('POSTGRES_USER', 'adruser'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        sslmode='require'
    )


MOCK_DECISIONS = [
    {
        "title": "Use PostgreSQL as Primary Database",
        "status": "accepted",
        "context": """We need to select a primary database for our new microservices architecture. The system will handle:
- High transaction volumes (10K+ TPS)
- Complex relational queries with joins
- ACID compliance requirements for financial data
- Need for JSON document storage for flexible schemas

We evaluated PostgreSQL, MySQL, MongoDB, and CockroachDB.""",
        "decision": """We will use PostgreSQL 16 as our primary database.

Key factors:
1. **ACID Compliance**: Full transaction support with serializable isolation
2. **JSON Support**: Native JSONB type for flexible document storage
3. **Performance**: Proven scalability with proper indexing and partitioning
4. **Extensions**: Rich ecosystem (PostGIS, pg_vector, TimescaleDB)
5. **Team Expertise**: Engineering team has deep PostgreSQL experience""",
        "consequences": """**Positive:**
- Strong data integrity guarantees
- Flexible schema evolution with JSONB columns
- Excellent tooling and monitoring support

**Negative:**
- Horizontal scaling requires more planning (read replicas, partitioning)
- Higher operational complexity than managed NoSQL solutions

**Risks:**
- Need to invest in DBA expertise for production operations""",
        "tags": ["database", "infrastructure", "postgresql"]
    },
    {
        "title": "Adopt Kubernetes for Container Orchestration",
        "status": "accepted",
        "context": """Our current deployment relies on manual VM provisioning and custom scripts. As we scale:
- Deployments take 2-4 hours
- No automated scaling during traffic spikes
- Inconsistent environments between staging and production
- Difficulty managing 20+ microservices

We need a container orchestration platform.""",
        "decision": """We will adopt Kubernetes (AKS on Azure) for all production workloads.

Implementation approach:
1. Start with stateless services migration
2. Use Helm charts for standardized deployments
3. Implement GitOps with ArgoCD
4. Gradual migration over 6 months""",
        "consequences": """**Positive:**
- Automated scaling based on metrics
- Self-healing with pod restarts
- Consistent dev/staging/prod environments
- 10-minute deployment cycles

**Negative:**
- Steep learning curve for operations team
- Increased infrastructure costs initially
- Complexity in debugging distributed systems

**Mitigations:**
- Invest in team training
- Start with non-critical services""",
        "tags": ["infrastructure", "kubernetes", "devops", "cloud"]
    },
    {
        "title": "Implement Event-Driven Architecture with Kafka",
        "status": "accepted",
        "context": """Our monolithic application uses synchronous REST calls between components, causing:
- Tight coupling between services
- Cascading failures during outages
- Difficulty scaling individual components
- No event replay capability for debugging

We need an asynchronous communication backbone.""",
        "decision": """We will implement Apache Kafka as our event streaming platform.

Architecture:
- Kafka cluster with 3 brokers (production)
- Schema Registry for Avro schemas
- Kafka Connect for database CDC
- Domain events published by each bounded context""",
        "consequences": """**Positive:**
- Loose coupling between services
- Event replay for debugging and recovery
- Natural audit log of system changes
- Enables real-time analytics

**Negative:**
- Eventual consistency requires mindset shift
- Additional operational complexity
- Need to handle idempotency in consumers

**Trade-offs:**
- Accepted eventual consistency for better scalability""",
        "tags": ["architecture", "messaging", "kafka", "event-driven"]
    },
    {
        "title": "Use TypeScript for All Frontend Development",
        "status": "accepted",
        "context": """Our frontend codebase has grown to 200K+ lines of JavaScript. Issues include:
- Runtime type errors in production
- Difficult refactoring without breaking changes
- Poor IDE support and autocomplete
- Inconsistent coding patterns across teams

We evaluated TypeScript, Flow, and staying with JavaScript.""",
        "decision": """All new frontend code will be written in TypeScript with strict mode enabled.

Migration strategy:
1. Enable TypeScript in existing projects with loose settings
2. New files must be .ts/.tsx
3. Gradually increase strictness
4. Complete migration within 12 months""",
        "consequences": """**Positive:**
- Catch errors at compile time
- Better IDE support and refactoring
- Self-documenting code through types
- Easier onboarding for new developers

**Negative:**
- Initial slowdown during migration
- Learning curve for developers new to TypeScript
- Build time increases slightly

**Success Metrics:**
- 50% reduction in type-related bugs within 6 months""",
        "tags": ["frontend", "typescript", "developer-experience"]
    },
    {
        "title": "Adopt Zero-Trust Security Model",
        "status": "accepted",
        "context": """Recent security audits revealed vulnerabilities in our network-perimeter security model:
- Lateral movement risk after initial breach
- VPN as single point of failure
- Difficulty supporting remote workforce
- Compliance gaps for SOC2 requirements

We need to modernize our security architecture.""",
        "decision": """We will implement a Zero-Trust security model with these components:

1. **Identity**: Azure AD with MFA for all users
2. **Device**: Endpoint detection and compliance checks
3. **Network**: Micro-segmentation with service mesh
4. **Application**: OAuth2/OIDC for all API access
5. **Data**: Encryption at rest and in transit""",
        "consequences": """**Positive:**
- Reduced blast radius of security incidents
- Better compliance posture (SOC2, ISO27001)
- Secure remote access without VPN
- Granular access control

**Negative:**
- Significant implementation effort (12-18 months)
- Increased authentication latency
- User friction during transition

**Investment:**
- $500K implementation cost
- 2 FTE security engineers""",
        "tags": ["security", "zero-trust", "compliance", "infrastructure"]
    },
    {
        "title": "Migrate to GraphQL for Mobile APIs",
        "status": "proposed",
        "context": """Our mobile apps suffer from:
- Over-fetching: REST endpoints return full objects
- Under-fetching: Multiple requests needed for screens
- Version management across iOS/Android
- Slow iteration on API changes

We're evaluating GraphQL as an alternative for mobile clients.""",
        "decision": """We propose adopting GraphQL for mobile APIs while keeping REST for server-to-server communication.

Proposed architecture:
- Apollo Server as GraphQL gateway
- Federation for microservice schemas
- Persisted queries for production
- REST endpoints remain for B2B integrations""",
        "consequences": """**Positive:**
- Precise data fetching reduces bandwidth
- Single request for complex screens
- Strong typing with schema
- Better developer experience

**Negative:**
- Learning curve for backend team
- Caching complexity vs REST
- N+1 query risks without DataLoader

**Open Questions:**
- Should we use subscriptions for real-time features?
- How to handle file uploads?""",
        "tags": ["api", "graphql", "mobile", "architecture"]
    },
    {
        "title": "Deprecate Legacy Authentication System",
        "status": "deprecated",
        "context": """Our custom OAuth implementation from 2018 has security concerns:
- Vulnerable to timing attacks
- No refresh token rotation
- Session management issues
- Not compliant with OAuth 2.1

We migrated to Auth0 in Q2 2024.""",
        "decision": """The legacy auth system is deprecated as of March 2024.

Migration completed:
- All applications moved to Auth0
- Legacy endpoints return 410 Gone
- Database credentials rotated
- Audit logs archived""",
        "consequences": """**Outcome:**
- Zero security incidents since migration
- 99.99% auth availability (up from 99.5%)
- Reduced maintenance burden

**Lessons Learned:**
- Should have migrated sooner
- Custom auth rarely justified""",
        "tags": ["security", "authentication", "deprecated"]
    },
    {
        "title": "Implement Feature Flags with LaunchDarkly",
        "status": "accepted",
        "context": """Our release process is hampered by:
- All-or-nothing deployments
- No ability to test in production safely
- Rollbacks require full redeploy
- A/B testing requires custom code

We need a feature flag system for controlled rollouts.""",
        "decision": """We will use LaunchDarkly for feature flag management.

Implementation:
- Server-side SDK for backend services
- Client-side SDK for web/mobile
- Integration with DataDog for metrics
- Approval workflow for production flags""",
        "consequences": """**Positive:**
- Gradual rollouts reduce risk
- Kill switch for problematic features
- A/B testing without code changes
- Faster incident response

**Negative:**
- Additional SaaS cost (~$2K/month)
- Flag debt if not cleaned up
- Complexity in testing all combinations

**Governance:**
- Flags must have expiration dates
- Monthly cleanup reviews""",
        "tags": ["devops", "feature-flags", "release-management"]
    },
    {
        "title": "Standardize on OpenTelemetry for Observability",
        "status": "accepted",
        "context": """Our observability stack is fragmented:
- Custom logging formats per service
- Mixed tracing (Jaeger, Zipkin, X-Ray)
- Metrics in Prometheus and CloudWatch
- No correlation between signals

We need a unified observability strategy.""",
        "decision": """We will standardize on OpenTelemetry for all observability signals.

Components:
- OTel Collector as central pipeline
- Auto-instrumentation where possible
- Grafana stack for visualization (Loki, Tempo, Mimir)
- Correlation IDs across all signals""",
        "consequences": """**Positive:**
- Vendor-neutral instrumentation
- Correlated logs, traces, and metrics
- Consistent debugging experience
- Future flexibility in backends

**Negative:**
- Migration effort from existing tools
- Some maturity gaps in OTel
- Learning curve for new SDK

**Timeline:**
- Q1: Collector deployment
- Q2: Service migration
- Q3: Legacy tool sunset""",
        "tags": ["observability", "monitoring", "devops", "opentelemetry"]
    },
    {
        "title": "Use Terraform for Infrastructure as Code",
        "status": "accepted",
        "context": """Infrastructure is provisioned through:
- Azure Portal (manual)
- ARM templates (inconsistent)
- Bash scripts (undocumented)

This leads to configuration drift and audit failures.""",
        "decision": """All infrastructure will be managed through Terraform.

Standards:
- Terraform Cloud for state management
- Module registry for reusable components
- PR-based workflow with plan review
- Sentinel policies for guardrails""",
        "consequences": """**Positive:**
- Reproducible infrastructure
- Version controlled changes
- Audit trail for compliance
- Disaster recovery capability

**Negative:**
- Learning curve for operators
- State file management complexity
- Some Azure features lag in provider

**Migration:**
- Import existing resources over 3 months""",
        "tags": ["infrastructure", "terraform", "iac", "devops"]
    }
]


def ensure_tenant_and_user(conn, domain: str):
    """Ensure tenant exists and has at least one user."""
    cur = conn.cursor()

    # Check if tenant has users
    cur.execute("SELECT id FROM users WHERE sso_domain = %s AND is_admin = TRUE LIMIT 1", (domain,))
    admin = cur.fetchone()

    if admin:
        return admin[0]

    # Create admin user for the tenant
    cur.execute("""
        INSERT INTO users (email, name, sso_domain, is_admin, created_at, updated_at, status)
        VALUES (%s, %s, %s, TRUE, NOW(), NOW(), 'active')
        ON CONFLICT (email) DO UPDATE SET updated_at = NOW()
        RETURNING id
    """, (f"admin@{domain}", "Demo Admin", domain))

    result = cur.fetchone()
    conn.commit()
    return result[0]


def seed_decisions(domain: str, dry_run: bool = False):
    """Seed mock decisions for a tenant."""
    conn = get_db_connection()

    try:
        user_id = ensure_tenant_and_user(conn, domain)
        print(f"Using user ID: {user_id} for domain: {domain}")

        cur = conn.cursor()

        # Check existing decisions
        cur.execute("SELECT COUNT(*) FROM architecture_decisions WHERE domain = %s", (domain,))
        existing_count = cur.fetchone()[0]

        if existing_count > 0:
            print(f"Domain {domain} already has {existing_count} decisions.")
            confirm = input("Delete existing and reseed? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Aborted.")
                return

            if not dry_run:
                cur.execute("DELETE FROM architecture_decisions WHERE domain = %s", (domain,))
                print(f"Deleted {cur.rowcount} existing decisions.")

        # Insert mock decisions
        for i, decision in enumerate(MOCK_DECISIONS):
            # Spread creation dates over past 6 months
            days_ago = random.randint(1, 180)
            created_at = datetime.now() - timedelta(days=days_ago)
            updated_at = created_at + timedelta(days=random.randint(0, min(30, days_ago)))

            decision_number = i + 1

            if dry_run:
                print(f"Would create: ADR-{decision_number:03d} - {decision['title']} ({decision['status']})")
            else:
                cur.execute("""
                    INSERT INTO architecture_decisions
                    (title, status, context, decision, consequences, decision_number,
                     domain, created_by_id, updated_by_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    decision['title'],
                    decision['status'],
                    decision['context'],
                    decision['decision'],
                    decision['consequences'],
                    decision_number,
                    domain,
                    user_id,
                    user_id,
                    created_at,
                    updated_at
                ))
                print(f"Created: ADR-{decision_number:03d} - {decision['title']} ({decision['status']})")

        if not dry_run:
            conn.commit()
            print(f"\nSuccessfully seeded {len(MOCK_DECISIONS)} decisions for {domain}")
        else:
            print(f"\nDry run: Would seed {len(MOCK_DECISIONS)} decisions for {domain}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Seed mock architecture decisions.')
    parser.add_argument('domain', help='Domain to seed decisions for (e.g., brandnewcorp.com)')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Show what would be created')

    args = parser.parse_args()
    seed_decisions(args.domain, dry_run=args.dry_run)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Seed demo data for screenshots with 3 company personas.

Creates:
1. Fashion Forward (urbanthread.co) - Retail fashion brand
2. CloudNova Technologies (cloudnova.io) - Tech company
3. Precision Manufacturing (precisionmfg.com) - Manufacturing company

Each company gets industry-specific decisions and a local login user.

Usage:
    python scripts/seed_screenshot_demo.py

Credentials (all use password: demo123):
    - urbanthread.co: demo@urbanthread.co
    - cloudnova.io: demo@cloudnova.io
    - precisionmfg.com: demo@precisionmfg.com
"""

import os
import sys
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, User, ArchitectureDecision, Tenant, TenantMembership, Space, GlobalRole, MaturityState
from werkzeug.security import generate_password_hash


# ============================================================================
# FASHION RETAIL DECISIONS (Urban Thread)
# ============================================================================

FASHION_DECISIONS = [
    {
        "title": "Implement Headless Commerce with Shopify Plus",
        "status": "accepted",
        "context": """Our monolithic e-commerce platform struggles with:
- Slow page load times (6+ seconds) impacting conversion
- Limited customization for seasonal campaigns
- Difficulty integrating with social commerce channels
- Mobile experience significantly worse than competitors

We need a modern e-commerce architecture that supports omnichannel selling.""",
        "decision": """We will adopt a headless commerce architecture using Shopify Plus as the backend.

Key components:
1. **Backend**: Shopify Plus Storefront API for inventory, orders, payments
2. **Frontend**: Next.js with Vercel Edge deployment
3. **CMS**: Contentful for campaign content
4. **Mobile**: React Native apps sharing web components

This allows us to maintain one backend while deploying optimized frontends per channel.""",
        "consequences": """**Positive:**
- Sub-2-second page loads on mobile
- Rapid campaign deployment (hours vs weeks)
- Native social commerce integration (Instagram, TikTok)
- 23% projected conversion improvement

**Negative:**
- Higher development complexity
- Need frontend engineers (previously PHP only)
- Increased operational costs initially

**Investment:** $180K implementation, 6-month timeline"""
    },
    {
        "title": "AI-Powered Size Recommendation Engine",
        "status": "accepted",
        "context": """Returns due to sizing issues cost us $2.4M annually:
- 34% of returns cite wrong size
- No standardization across brands we carry
- Customer frustration leading to cart abandonment
- Competitors offering virtual try-on features

We need intelligent sizing recommendations.""",
        "decision": """Deploy a machine learning-based size recommendation system.

Implementation:
1. **Data Collection**: Purchase history, return reasons, body measurements (optional)
2. **Model**: Collaborative filtering + garment measurements
3. **UI**: Size confidence indicator on product pages
4. **Integration**: Returns feedback loop for model improvement

Vendor: Fit Analytics (acquired by Snap) integration with custom fallback model.""",
        "consequences": """**Positive:**
- Projected 40% reduction in size-related returns
- Improved customer confidence (NPS increase)
- Data asset for future personalization
- Competitive feature parity

**Negative:**
- Privacy considerations for body data
- Initial accuracy ~75% until model trains
- Integration complexity with multiple brands

**ROI:** Expected $1.2M annual savings within 18 months"""
    },
    {
        "title": "Adopt Sustainable Packaging Standards",
        "status": "accepted",
        "context": """Customer demand for sustainability is increasing:
- 67% of customers prefer eco-friendly brands
- Current plastic packaging generates negative social media
- EU regulations coming in 2025
- Competitors announcing green initiatives

We need to transition to sustainable packaging.""",
        "decision": """All packaging will transition to certified sustainable materials by Q4 2024.

Standards:
1. **Materials**: FSC-certified recycled cardboard, compostable mailers
2. **Sizing**: Right-sized boxes to reduce void fill
3. **Certification**: B Corp certification target
4. **Communication**: QR codes linking to sustainability info

Supplier: Noissue for custom branded sustainable packaging.""",
        "consequences": """**Positive:**
- Brand alignment with customer values
- Marketing differentiation
- EU compliance ahead of deadline
- Reduced shipping costs (lighter materials)

**Negative:**
- 12% increase in packaging costs
- Supply chain complexity (new vendors)
- Customer education needed

**Investment:** $85K annual increase, offset by shipping savings"""
    },
    {
        "title": "Real-Time Inventory Sync Across Channels",
        "status": "accepted",
        "context": """Inventory discrepancies cause:
- Overselling during flash sales (2-3 incidents/month)
- Lost sales from phantom stock-outs
- Manual reconciliation taking 20 hours/week
- Customer complaints about order cancellations

We need real-time inventory visibility.""",
        "decision": """Implement event-driven inventory management with real-time sync.

Architecture:
1. **Source of Truth**: Shopify Plus inventory
2. **Event Bus**: AWS EventBridge for inventory events
3. **Sync**: Sub-second updates to all channels (web, mobile, marketplaces)
4. **Safety Stock**: Dynamic buffers based on demand signals

All channel inventory queries go through a caching layer with 5-second TTL.""",
        "consequences": """**Positive:**
- Zero overselling incidents
- 15% increase in available-to-sell inventory
- Eliminate manual reconciliation
- Enable flash sales confidence

**Negative:**
- Infrastructure complexity
- Need for monitoring/alerting
- Training for operations team

**Investment:** $45K implementation + $2K/month infrastructure"""
    },
    {
        "title": "Influencer Attribution Platform",
        "status": "proposed",
        "context": """Influencer marketing spend is $800K/year but:
- No reliable attribution (last-click only)
- Cannot differentiate micro vs macro influencer ROI
- Manual tracking via spreadsheets
- Agency fees for campaign management

We need data-driven influencer marketing.""",
        "decision": """Build custom influencer attribution platform.

Proposed components:
1. **Tracking**: Unique URLs + promo codes per influencer
2. **Attribution**: Multi-touch model with view-through
3. **Dashboard**: Real-time campaign performance
4. **Payments**: Automated commission calculations

Evaluate: Build vs. buy (Grin, CreatorIQ, custom).""",
        "consequences": """**Positive:**
- ROI visibility per influencer
- Data-driven budget allocation
- Reduce agency dependency
- Scale micro-influencer program

**Negative:**
- Build option: 6+ month development
- Buy option: $50K+ annual platform cost
- Integration with existing analytics

**Open Questions:**
- In-house team capacity?
- Agency contract status?"""
    },
    {
        "title": "Deprecate Legacy POS System",
        "status": "deprecated",
        "context": """Our 2018 point-of-sale system has reached end of life:
- No longer supported by vendor
- Cannot integrate with new payment methods (Apple Pay, BNPL)
- Security vulnerabilities identified
- Hardware replacement parts unavailable

Migration to Shopify POS completed Q1 2024.""",
        "decision": """Legacy POS system is deprecated as of March 2024.

Migration completed:
- All 12 retail locations on Shopify POS
- Unified inventory with online
- Staff trained on new system
- Historical data archived

Legacy hardware donated to e-waste recycling.""",
        "consequences": """**Outcome:**
- Unified online/offline experience
- Faster checkout (tap to pay)
- Real-time inventory accuracy
- $30K annual maintenance savings

**Lessons Learned:**
- Should have migrated sooner
- Staff adoption was smoother than expected"""
    },
    {
        "title": "Customer Loyalty Program Redesign",
        "status": "accepted",
        "context": """Current loyalty program underperforms:
- 12% redemption rate (industry avg: 25%)
- Points-based system feels transactional
- No emotional connection to brand
- Competitors offering experiential rewards

We need a modern loyalty approach.""",
        "decision": """Launch tier-based loyalty program with experiential rewards.

Program structure:
1. **Tiers**: Thread (base), Weave (100+ points), Fabric (500+ points)
2. **Earn**: $1 = 1 point, bonus for reviews/referrals
3. **Redeem**: Mix of discounts + exclusive experiences
4. **Experiences**: Early access, stylist sessions, events

Platform: Yotpo Loyalty integration with Shopify.""",
        "consequences": """**Positive:**
- Projected 40% increase in repeat purchases
- Higher-value experiential rewards build brand affinity
- Social sharing of experiences
- Customer data for personalization

**Negative:**
- Cost of experiences
- Program management complexity
- Risk of tier gaming

**Investment:** $120K platform + $50K annual experiences budget"""
    },
    {
        "title": "Visual Search for Product Discovery",
        "status": "proposed",
        "context": """Customers struggle to find products:
- 40% of mobile sessions end without product view
- Text search fails for style/aesthetic queries
- Competitors have visual search features
- Social media drives image-based discovery

We need visual search capabilities.""",
        "decision": """Implement visual search allowing customers to upload photos.

Proposed solution:
1. **ML Model**: Google Vision API for initial launch
2. **Index**: All product images with style attributes
3. **UI**: Camera icon in search bar, drag-and-drop
4. **Results**: Similar products with style match score

Evaluate custom model training after usage data available.""",
        "consequences": """**Positive:**
- Unlock image-based discovery
- Reduce search abandonment
- Support "shop the look" features
- Differentiate from text-only competitors

**Negative:**
- API costs scale with usage
- Accuracy varies by category
- Mobile camera permissions required

**Cost:** $15K implementation + usage-based API costs"""
    }
]


# ============================================================================
# TECH COMPANY DECISIONS (CloudNova Technologies)
# ============================================================================

TECH_DECISIONS = [
    {
        "title": "Migrate to Multi-Cloud Architecture",
        "status": "accepted",
        "context": """Our AWS-only infrastructure creates risks:
- Vendor lock-in with $2.5M annual spend
- Single region availability (us-east-1 outages)
- Limited negotiating leverage
- Compliance requirements for data residency

We need cloud diversification strategy.""",
        "decision": """Adopt multi-cloud architecture with workload-appropriate placement.

Strategy:
1. **Primary**: AWS remains for stateful workloads
2. **Secondary**: GCP for ML/AI workloads (better TPU pricing)
3. **Edge**: Cloudflare Workers for latency-sensitive
4. **Abstraction**: Kubernetes (EKS/GKE) for portability

Control plane: HashiCorp suite (Terraform, Vault, Consul).""",
        "consequences": """**Positive:**
- 15% cost reduction through competitive pricing
- Improved availability (multi-region active-active)
- Access to best-in-class services per cloud
- Reduced vendor dependency

**Negative:**
- Operational complexity increase
- Team needs multi-cloud expertise
- Some services not portable

**Timeline:** 18-month migration, critical workloads last"""
    },
    {
        "title": "Implement Zero-Trust Network Architecture",
        "status": "accepted",
        "context": """Recent security landscape demands changes:
- Remote workforce increased attack surface
- Perimeter security model outdated
- SOC2 Type II audit findings
- VPN bottlenecks during high-traffic periods

We need modern security architecture.""",
        "decision": """Implement zero-trust security model across all systems.

Components:
1. **Identity**: Okta for SSO with MFA everywhere
2. **Device**: CrowdStrike for endpoint verification
3. **Network**: Micro-segmentation via service mesh (Istio)
4. **Access**: RBAC with just-in-time privilege escalation
5. **Data**: Encryption everywhere (at rest + in transit)

Principle: Never trust, always verify.""",
        "consequences": """**Positive:**
- Reduced breach impact (lateral movement blocked)
- Compliance posture improvement
- Secure remote access without VPN
- Audit trail for all access

**Negative:**
- 12-month implementation timeline
- User friction during transition
- Increased authentication latency

**Investment:** $400K implementation + $150K annual licensing"""
    },
    {
        "title": "Adopt GitOps for Infrastructure Management",
        "status": "accepted",
        "context": """Infrastructure changes are error-prone:
- Manual kubectl commands in production
- No audit trail for infrastructure changes
- Drift between environments
- Rollback requires tribal knowledge

We need declarative infrastructure management.""",
        "decision": """All infrastructure managed through GitOps workflows.

Implementation:
1. **Tool**: ArgoCD for Kubernetes resources
2. **Repo Structure**: Monorepo with environment overlays
3. **Process**: PR-based changes with automated drift detection
4. **Secrets**: External Secrets Operator with Vault backend

Policy: No manual changes to production clusters.""",
        "consequences": """**Positive:**
- Full audit trail via git history
- Self-healing drift correction
- Reproducible environments
- Faster incident response (git revert)

**Negative:**
- Learning curve for operations
- Initial migration effort
- Emergency changes require PR workflow

**Governance:** Break-glass procedure for emergencies"""
    },
    {
        "title": "Build Internal Developer Platform",
        "status": "accepted",
        "context": """Developer productivity metrics are concerning:
- 4+ hours average to set up new service
- Inconsistent CI/CD pipelines across teams
- Duplicate infrastructure code
- Platform team bottleneck for deployments

We need self-service developer experience.""",
        "decision": """Build internal developer platform (IDP) using Backstage.

Capabilities:
1. **Service Catalog**: Discover and document all services
2. **Templates**: Golden paths for new services
3. **Scaffolding**: One-click service creation
4. **Docs**: Centralized technical documentation
5. **Metrics**: DORA metrics per team

Platform team provides templates, product teams self-serve.""",
        "consequences": """**Positive:**
- New service setup: 4 hours to 15 minutes
- Consistent standards across teams
- Reduced platform team toil
- Improved developer satisfaction

**Negative:**
- 6-month build time for MVP
- Ongoing maintenance investment
- Change management for adoption

**Team:** 3 FTE platform engineers dedicated"""
    },
    {
        "title": "Standardize on OpenTelemetry",
        "status": "accepted",
        "context": """Observability is fragmented:
- 5 different logging formats
- Mixed tracing (Jaeger, X-Ray, Datadog)
- No correlation between signals
- $80K/month observability tool spend

We need unified observability strategy.""",
        "decision": """Standardize all services on OpenTelemetry.

Architecture:
1. **SDK**: OTel auto-instrumentation per language
2. **Collector**: Central OTel Collector pipeline
3. **Backend**: Grafana stack (Loki, Tempo, Mimir)
4. **Correlation**: Trace ID propagation across all signals

All services must emit traces, metrics, and structured logs.""",
        "consequences": """**Positive:**
- Vendor-neutral instrumentation
- Correlated debugging experience
- 40% reduction in observability costs
- Future flexibility in backends

**Negative:**
- Migration from existing tools
- Initial accuracy tuning needed
- Team training required

**Timeline:** 6-month migration with quarterly milestones"""
    },
    {
        "title": "Implement Feature Flag System",
        "status": "accepted",
        "context": """Release management is high-risk:
- All-or-nothing deployments
- Rollbacks require full redeploy
- Cannot test in production safely
- No ability for gradual rollouts

We need controlled feature releases.""",
        "decision": """Adopt LaunchDarkly for feature flag management.

Implementation:
1. **Server SDK**: All backend services
2. **Client SDK**: Web and mobile apps
3. **Targeting**: User segments, percentages, environments
4. **Integrations**: DataDog metrics, Slack notifications

All new features behind flags by default.""",
        "consequences": """**Positive:**
- Safe production testing
- Instant kill switch for issues
- Gradual rollouts (1% -> 100%)
- A/B testing capability

**Negative:**
- $3K/month licensing
- Flag debt if not cleaned up
- Testing complexity

**Governance:** Flags expire after 90 days, monthly cleanup"""
    },
    {
        "title": "Migrate Authentication to Passkeys",
        "status": "proposed",
        "context": """Password-based auth has issues:
- 15% of support tickets are password resets
- Credential stuffing attacks increasing
- User friction at login
- MFA adoption only 45%

Passkeys offer passwordless future.""",
        "decision": """Propose phased migration to WebAuthn/Passkeys.

Phases:
1. **Phase 1**: Passkey as additional 2FA option
2. **Phase 2**: Passkey-first with password fallback
3. **Phase 3**: Passwordless for new accounts
4. **Phase 4**: Password deprecation (optional)

Support: Apple, Google, Microsoft ecosystems.""",
        "consequences": """**Positive:**
- Phishing-resistant authentication
- Better user experience
- Reduced support burden
- Industry-leading security

**Negative:**
- Device dependency for users
- Account recovery complexity
- Browser support variations

**Open Questions:**
- Recovery flow design?
- Enterprise SSO integration?"""
    },
    {
        "title": "Deprecate Monolith API",
        "status": "deprecated",
        "context": """The original monolithic API has been superseded:
- All functionality migrated to microservices
- Maintaining two codebases
- Security vulnerabilities in legacy code
- Performance bottleneck

Microservices migration completed Q2 2024.""",
        "decision": """Monolith API is deprecated as of June 2024.

Migration completed:
- All endpoints mapped to microservices
- API gateway routing updated
- Legacy database read-only
- Traffic confirmed zero

Codebase archived for reference.""",
        "consequences": """**Outcome:**
- 60% latency improvement
- Independent service scaling
- Faster feature development
- Reduced maintenance burden

**Lessons Learned:**
- Strangler fig pattern worked well
- Should have sunset earlier"""
    },
    {
        "title": "Adopt Rust for Performance-Critical Services",
        "status": "accepted",
        "context": """Some services have strict performance requirements:
- Real-time bidding (< 50ms latency)
- Data processing pipelines (throughput)
- Memory-constrained edge deployments
- GC pauses in Go causing latency spikes

We need a systems language option.""",
        "decision": """Rust approved for performance-critical services.

Criteria for Rust adoption:
1. Latency budget < 10ms p99
2. Memory-constrained environments
3. CPU-intensive data processing
4. Team has Rust experience

Go remains default for standard services.""",
        "consequences": """**Positive:**
- Zero-cost abstractions
- Memory safety without GC
- Predictable latency
- Strong type system

**Negative:**
- Steeper learning curve
- Longer development time
- Smaller hiring pool

**Governance:** Architecture review required for new Rust services"""
    },
    {
        "title": "Implement Data Mesh Architecture",
        "status": "proposed",
        "context": """Centralized data platform bottleneck:
- 6-week average wait for new datasets
- Data engineering team overwhelmed
- Domain knowledge lost in translation
- Data quality issues from disconnected ownership

We need decentralized data ownership.""",
        "decision": """Propose data mesh architecture adoption.

Principles:
1. **Domain Ownership**: Teams own their data products
2. **Data as Product**: SLAs, documentation, quality
3. **Self-Serve Platform**: Standardized tools/templates
4. **Federated Governance**: Shared policies, local execution

Platform: Databricks Unity Catalog for data marketplace.""",
        "consequences": """**Positive:**
- Faster time to data availability
- Domain expertise retained
- Scalable data organization
- Clear ownership model

**Negative:**
- Significant organizational change
- Training investment
- Initial quality inconsistency

**Open Questions:**
- Team readiness assessment?
- Governance model details?"""
    }
]


# ============================================================================
# MANUFACTURING DECISIONS (Precision Manufacturing)
# ============================================================================

MANUFACTURING_DECISIONS = [
    {
        "title": "Implement IoT Sensors for Predictive Maintenance",
        "status": "accepted",
        "context": """Unplanned downtime costs $150K/day:
- Reactive maintenance model
- Equipment failures during production runs
- No visibility into machine health
- Spare parts inventory guesswork

We need predictive maintenance capability.""",
        "decision": """Deploy IoT sensor network across critical equipment.

Implementation:
1. **Sensors**: Vibration, temperature, power consumption
2. **Edge**: Local processing for real-time alerts
3. **Cloud**: AWS IoT for data aggregation
4. **ML**: Anomaly detection models per machine type
5. **Integration**: CMMS for work order automation

Priority: CNC machines, hydraulic presses, conveyor systems.""",
        "consequences": """**Positive:**
- 35% reduction in unplanned downtime
- Optimized spare parts inventory
- Extended equipment lifespan
- Data-driven maintenance scheduling

**Negative:**
- $500K initial sensor deployment
- Need for data engineering resources
- Model training requires 6+ months data

**ROI:** 18-month payback based on downtime reduction"""
    },
    {
        "title": "Adopt MES for Real-Time Production Visibility",
        "status": "accepted",
        "context": """Production visibility is limited:
- Paper-based tracking on shop floor
- Shift reports available next day
- No real-time OEE metrics
- Quality issues discovered late

We need manufacturing execution system.""",
        "decision": """Implement Plex MES for all production lines.

Capabilities:
1. **Tracking**: Real-time work order status
2. **Quality**: Inline inspection data capture
3. **Labor**: Operator time tracking
4. **Genealogy**: Full traceability per unit
5. **KPIs**: OEE, cycle time, scrap rate dashboards

Integration with existing ERP (SAP) for order sync.""",
        "consequences": """**Positive:**
- Real-time production visibility
- 15% OEE improvement projected
- Quality traceability for recalls
- Data-driven continuous improvement

**Negative:**
- $300K implementation cost
- Change management for operators
- 12-month full deployment

**Training:** 40 hours per operator role"""
    },
    {
        "title": "Implement Digital Twin for Process Optimization",
        "status": "accepted",
        "context": """Process optimization is trial-and-error:
- Physical experiments expensive
- No simulation before production changes
- Limited understanding of parameter interactions
- Competitors using advanced simulation

We need digital twin capabilities.""",
        "decision": """Build digital twin for injection molding process.

Components:
1. **Physics Model**: Moldflow simulation integration
2. **Data Model**: ML from historical production data
3. **Real-Time**: Sensor data for twin synchronization
4. **Optimization**: Parameter tuning recommendations
5. **Visualization**: 3D process visualization

Vendor: Siemens MindSphere platform with custom models.""",
        "consequences": """**Positive:**
- 25% faster process optimization
- Reduced scrap during new product intro
- Virtual experimentation capability
- Knowledge capture for process

**Negative:**
- Specialized skills required
- Model accuracy dependent on data quality
- Integration complexity

**Investment:** $250K first process, $50K each additional"""
    },
    {
        "title": "Standardize on OPC-UA for Machine Connectivity",
        "status": "accepted",
        "context": """Machine connectivity is fragmented:
- 12 different protocols (Modbus, Profinet, proprietary)
- Custom integrations per machine
- No standardization for new equipment
- Vendor lock-in on connectivity

We need standard connectivity protocol.""",
        "decision": """All new equipment must support OPC-UA.

Standards:
1. **Protocol**: OPC-UA as mandatory interface
2. **Information Model**: ISA-95 compliant
3. **Security**: Certificate-based authentication
4. **Gateway**: OPC-UA to MQTT for cloud integration

Existing equipment: Gateway retrofit where ROI positive.""",
        "consequences": """**Positive:**
- Vendor-neutral machine data access
- Simplified integration architecture
- Industry standard compliance
- Reduced connectivity development

**Negative:**
- Legacy equipment limitations
- Gateway costs for retrofit
- Supplier negotiation required

**Policy:** RFQ requirement for all new equipment"""
    },
    {
        "title": "Implement Automated Quality Inspection",
        "status": "accepted",
        "context": """Manual inspection has limitations:
- 5% defect escape rate
- Inspector fatigue affects accuracy
- Cannot scale with volume increases
- Subjective criteria inconsistency

We need automated inspection capability.""",
        "decision": """Deploy computer vision systems for quality inspection.

Implementation:
1. **Hardware**: High-speed cameras, structured lighting
2. **Software**: Cognex VisionPro with deep learning
3. **Integration**: Reject diverter automation
4. **Feedback**: Real-time process adjustment signals

Initial deployment: Surface defect detection on painted parts.""",
        "consequences": """**Positive:**
- 99.5% defect detection accuracy
- Consistent inspection criteria
- 3x inspection throughput
- Data for root cause analysis

**Negative:**
- $400K for initial deployment
- Lighting/camera tuning complexity
- Model training for new products

**ROI:** 24-month payback from reduced escapes and labor"""
    },
    {
        "title": "Migrate ERP to SAP S/4HANA",
        "status": "accepted",
        "context": """Current SAP ECC reaching end of support (2027):
- Customizations prevent upgrade
- Performance issues with reporting
- No real-time analytics
- Modern integration challenges

We must migrate to S/4HANA.""",
        "decision": """Greenfield S/4HANA implementation with fit-to-standard approach.

Approach:
1. **Strategy**: Greenfield (not conversion) to reduce technical debt
2. **Customizations**: Evaluate each; adopt standard where possible
3. **Data**: Cleanse and migrate master data only
4. **Timeline**: 24-month implementation
5. **Partner**: Accenture for implementation

Key modules: MM, PP, QM, PM, SD, FI/CO.""",
        "consequences": """**Positive:**
- Modern platform with vendor support
- Real-time analytics (Fiori)
- Reduced customization debt
- Cloud deployment option

**Negative:**
- $2.5M implementation cost
- Significant change management
- 24-month timeline

**Risk Mitigation:** Parallel run period, phased cutover"""
    },
    {
        "title": "Implement Track and Trace for Serialization",
        "status": "accepted",
        "context": """Traceability requirements increasing:
- Customer audit requests for genealogy
- Recall scope difficult to determine
- Counterfeit concerns in supply chain
- Regulatory compliance (automotive)

We need unit-level traceability.""",
        "decision": """Implement serialization with track and trace.

Solution:
1. **Marking**: 2D DataMatrix codes on all parts
2. **Scanning**: Process step verification
3. **Database**: Complete genealogy per serial
4. **Portal**: Customer access to trace data
5. **Integration**: MES for process data linkage

Standard: AIAG B-17 traceability requirements.""",
        "consequences": """**Positive:**
- Full unit-level traceability
- Recall scope reduction (95%+ precision)
- Customer audit compliance
- Supply chain visibility

**Negative:**
- Marking equipment investment
- Process time increase (minimal)
- Database storage requirements

**Investment:** $200K equipment + ongoing storage"""
    },
    {
        "title": "Adopt Collaborative Robots for Assembly",
        "status": "proposed",
        "context": """Assembly operations face challenges:
- Labor shortage for repetitive tasks
- Ergonomic injury concerns
- Quality consistency issues
- Overtime costs during demand spikes

We're evaluating collaborative robots.""",
        "decision": """Propose cobots for repetitive assembly tasks.

Evaluation criteria:
1. **Tasks**: Pick-and-place, screw driving, inspection assist
2. **ROI**: Minimum 2-year payback
3. **Safety**: No guarding required (speed/force limited)
4. **Flexibility**: Quick changeover between products

Pilot: Universal Robots UR10e for subassembly station.""",
        "consequences": """**Positive:**
- Consistent output quality
- Reduced ergonomic injuries
- Flexible automation (not fixed)
- Operator skill augmentation

**Negative:**
- $75K per cobot cell
- Programming skills required
- Not suitable for all tasks

**Open Questions:**
- Union considerations?
- Training program design?"""
    },
    {
        "title": "Deprecate Legacy SCADA System",
        "status": "deprecated",
        "context": """Legacy Wonderware SCADA has limitations:
- Windows XP dependencies (security risk)
- No modern integration capabilities
- Vendor support ending
- Limited mobile access

Migrated to Ignition platform Q4 2023.""",
        "decision": """Legacy SCADA system is deprecated as of December 2023.

Migration completed:
- All 8 SCADA stations on Ignition
- Historical data migrated (10 years)
- Mobile dashboards deployed
- Legacy hardware decommissioned

Security risk eliminated.""",
        "consequences": """**Outcome:**
- Modern, supported platform
- Mobile access for supervisors
- Improved integration capabilities
- Eliminated security vulnerabilities

**Lessons Learned:**
- Should have migrated sooner
- Ignition licensing model better for scaling"""
    },
    {
        "title": "Implement Energy Management System",
        "status": "accepted",
        "context": """Energy costs are $1.2M annually:
- No visibility into consumption patterns
- Peak demand charges significant
- Sustainability reporting requirements
- Opportunity for cost reduction

We need energy monitoring and optimization.""",
        "decision": """Deploy energy management system across facility.

Components:
1. **Metering**: Smart meters on all equipment > 10kW
2. **Monitoring**: Real-time energy dashboard
3. **Analytics**: Pattern analysis, anomaly detection
4. **Control**: Peak shaving through load scheduling
5. **Reporting**: Carbon footprint reporting

Platform: Schneider Electric EcoStruxure.""",
        "consequences": """**Positive:**
- 15% energy cost reduction projected
- Peak demand charge optimization
- Sustainability reporting capability
- Anomaly detection (air leaks, etc.)

**Negative:**
- $150K implementation cost
- Metering installation disruption
- IT/OT convergence complexity

**ROI:** 18-month payback from energy savings"""
    }
]


def create_tenant_with_user(domain, company_name, email, user_name, password):
    """Create a tenant, user, membership, and default space."""

    # 1. Create or get Tenant
    tenant = Tenant.query.filter_by(domain=domain).first()
    if tenant:
        print(f"  Tenant {domain} already exists, updating...")
        tenant.name = company_name
        tenant.status = 'active'
        tenant.maturity_state = MaturityState.MATURE
    else:
        tenant = Tenant(
            domain=domain,
            name=company_name,
            status='active',
            maturity_state=MaturityState.MATURE,
            created_at=datetime.utcnow()
        )
        db.session.add(tenant)
        db.session.flush()  # Get the tenant ID
        print(f"  Created tenant: {domain}")

    # 2. Create or get User
    user = User.query.filter_by(email=email).first()
    if user:
        print(f"  User {email} already exists, updating...")
        user.name = user_name
        user.password_hash = generate_password_hash(password)
        user.is_admin = True
    else:
        user = User(
            email=email,
            name=user_name,
            sso_domain=domain,
            password_hash=generate_password_hash(password),
            auth_type='local',
            is_admin=True,
            email_verified=True,
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.flush()  # Get the user ID
        print(f"  Created user: {email}")

    # 3. Create TenantMembership (link user to tenant as ADMIN)
    membership = TenantMembership.query.filter_by(user_id=user.id, tenant_id=tenant.id).first()
    if membership:
        print(f"  Membership already exists, updating role...")
        membership.global_role = GlobalRole.ADMIN
    else:
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            global_role=GlobalRole.ADMIN,
            joined_at=datetime.utcnow()
        )
        db.session.add(membership)
        print(f"  Created membership: {email} -> {domain} (ADMIN)")

    # 4. Create default Space if not exists
    default_space = Space.query.filter_by(tenant_id=tenant.id, is_default=True).first()
    if not default_space:
        default_space = Space(
            tenant_id=tenant.id,
            name='General',
            description='Default space for all decisions',
            is_default=True,
            created_by_id=user.id,
            created_at=datetime.utcnow()
        )
        db.session.add(default_space)
        print(f"  Created default space: General")

    db.session.commit()
    return user, tenant


def seed_decisions_for_domain(domain, decisions, user):
    """Seed decisions for a specific domain."""
    # Delete existing decisions for this domain
    existing = ArchitectureDecision.query.filter_by(domain=domain).all()
    if existing:
        print(f"  Deleting {len(existing)} existing decisions...")
        for d in existing:
            db.session.delete(d)
        db.session.commit()

    for i, decision_data in enumerate(decisions):
        # Create varied dates
        days_ago = random.randint(7, 180)
        created_at = datetime.utcnow() - timedelta(days=days_ago)
        updated_at = created_at + timedelta(days=random.randint(0, min(30, days_ago)))

        decision = ArchitectureDecision(
            title=decision_data['title'],
            status=decision_data['status'],
            context=decision_data['context'],
            decision=decision_data['decision'],
            consequences=decision_data['consequences'],
            decision_number=i + 1,
            domain=domain,
            created_by_id=user.id,
            updated_by_id=user.id,
            created_at=created_at,
            updated_at=updated_at
        )
        db.session.add(decision)
        print(f"    Created: ADR-{i+1:03d} - {decision_data['title'][:50]}...")

    db.session.commit()


def main():
    """Seed all demo companies."""
    print("=" * 60)
    print("Seeding Screenshot Demo Data")
    print("=" * 60)

    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

        companies = [
            {
                "domain": "urbanthread.co",
                "company": "Urban Thread",
                "industry": "Fashion Retail",
                "email": "demo@urbanthread.co",
                "name": "Sarah Mitchell",
                "decisions": FASHION_DECISIONS
            },
            {
                "domain": "cloudnova.io",
                "company": "CloudNova Technologies",
                "industry": "Technology",
                "email": "demo@cloudnova.io",
                "name": "Alex Chen",
                "decisions": TECH_DECISIONS
            },
            {
                "domain": "precisionmfg.com",
                "company": "Precision Manufacturing",
                "industry": "Manufacturing",
                "email": "demo@precisionmfg.com",
                "name": "Michael Torres",
                "decisions": MANUFACTURING_DECISIONS
            }
        ]

        password = "demo123"

        for company in companies:
            print(f"\n{company['company']} ({company['industry']})")
            print("-" * 40)

            # Create tenant, user, membership, and default space
            user, tenant = create_tenant_with_user(
                company['domain'],
                company['company'],
                company['email'],
                company['name'],
                password
            )

            # Seed decisions
            seed_decisions_for_domain(
                company['domain'],
                company['decisions'],
                user
            )
            print(f"  Decisions: {len(company['decisions'])} created")

        print("\n" + "=" * 60)
        print("DEMO CREDENTIALS (password for all: demo123)")
        print("=" * 60)
        for company in companies:
            print(f"\n{company['company']}:")
            print(f"  URL: http://localhost:4200/{company['domain']}")
            print(f"  Email: {company['email']}")
            print(f"  Password: {password}")

        print("\n" + "=" * 60)
        print("Demo data seeded successfully!")
        print("=" * 60)


if __name__ == '__main__':
    main()

# Fresh Public Repository Setup

This document describes how to create the fresh public DecisionRecords repository for open source release.

## Overview

The goal is to create a clean public repository without git history that might contain sensitive information, while keeping the Enterprise Edition code in a private submodule.

```
DecisionRecordsORG/
├── DecisionRecords (PUBLIC)     # Open source core
│   ├── app.py, models.py, etc.
│   ├── frontend/
│   ├── docs/
│   └── ee/ → submodule         # Points to private repo
│
└── ee (PRIVATE)                 # Enterprise Edition
    ├── backend/
    ├── frontend/
    ├── marketing/
    └── deployment/
```

## Prerequisites

1. GitHub organization `DecisionRecordsORG` created
2. Access to create repositories in the organization
3. SSH keys configured for GitHub

## Step 1: Create the Private EE Repository

```bash
# Create the ee repository on GitHub (private)
gh repo create DecisionRecordsORG/ee --private --description "Decision Records Enterprise Edition"

# Push current ee/ content
cd ee
git remote add origin git@github.com:DecisionRecordsORG/ee.git
git push -u origin main
cd ..
```

## Step 2: Create Fresh Public Repository

```bash
# Create a clean directory
mkdir -p ~/DecisionRecords-public
cd ~/DecisionRecords-public

# Initialize new git repo
git init

# Copy files (excluding items in .gitignore-public)
rsync -av \
  --exclude-from='/path/to/architecture-decisions/.gitignore-public' \
  /path/to/architecture-decisions/ .

# Remove ee/ directory (will be added as submodule)
rm -rf ee/

# Initial commit
git add .
git commit -m "Initial open source release

Decision Records - Open source architecture decision records platform

Features:
- Architecture Decision Records (ADR) management
- Multi-tenant workspaces
- WebAuthn/Passkey authentication
- OIDC/SSO integration
- Role-based access control
- Self-hosted with Docker

License: BSL 1.1 (converts to Apache 2.0 after 4 years)"
```

## Step 3: Add EE as Submodule

```bash
# Add ee as a git submodule
git submodule add git@github.com:DecisionRecordsORG/ee.git ee

# Commit the submodule reference
git commit -m "Add Enterprise Edition as submodule"
```

## Step 4: Create GitHub Repository and Push

```bash
# Create the public repository
gh repo create DecisionRecordsORG/DecisionRecords --public \
  --description "Open source architecture decision records platform" \
  --homepage "https://decisionrecords.org"

# Push to GitHub
git remote add origin git@github.com:DecisionRecordsORG/DecisionRecords.git
git push -u origin main
```

## Step 5: Configure Repository Settings

### Branch Protection (main)
- Require pull request reviews
- Require status checks (CI)
- Require branches to be up to date

### Secrets (Settings > Secrets > Actions)
| Secret | Description |
|--------|-------------|
| `EE_REPO_TOKEN` | PAT with access to private ee repo |
| `AZURE_CREDENTIALS` | Azure service principal (for EE deploys) |
| `CLOUDFLARE_API_TOKEN` | Cloudflare cache purge (for EE deploys) |

### Repository Topics
Add topics: `architecture-decisions`, `adr`, `documentation`, `self-hosted`, `flask`, `angular`

## Step 6: Verify Builds

### Community Edition (no ee/)
```bash
# Clone without submodule
git clone https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords

# Build and test
docker build -f Dockerfile.community -t decision-records:ce .
docker run -p 3000:8000 -e SECRET_KEY=test decision-records:ce
```

### Enterprise Edition (with ee/)
```bash
# Clone with submodule (requires access)
git clone --recurse-submodules git@github.com:DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords

# Build EE
docker build -f ee/deployment/Dockerfile.production -t decision-records:ee .
```

## Step 7: Post-Setup Tasks

1. **Enable GitHub Discussions** - For community support
2. **Create issue templates** - Bug report, feature request
3. **Set up GitHub Pages** - For documentation (optional)
4. **Create first release** - Tag v1.14.2 and trigger release workflow
5. **Update README badges** - Point to new repo URLs
6. **Archive old repository** - Make private or delete

## Verification Checklist

- [ ] Public repo has no git history with secrets
- [ ] ee/ is a working submodule
- [ ] CI workflow passes (test-backend, build-frontend, build-docker)
- [ ] Docker CE image builds successfully
- [ ] Docker EE image builds successfully (with submodule)
- [ ] Release workflow publishes to GHCR
- [ ] README links work
- [ ] License files present (BSL 1.1 + ee/LICENSE)

## Rollback Plan

If issues are discovered after public release:

1. Make public repo private temporarily
2. Fix issues in the original repository
3. Re-run the fresh repo creation process
4. Make public again

Keep the original `architecture-decisions` repository for at least 30 days after public release as a backup.

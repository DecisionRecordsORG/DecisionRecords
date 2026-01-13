# Repository Setup Guide

This guide explains how to set up the GitHub organization and repositories for the Decision Records Open Core project.

## Overview

Decision Records uses a **Public Repo with Private Submodule** model:

| Repository | Visibility | Contents |
|------------|------------|----------|
| `DecisionRecordsORG/DecisionRecords` | **Public** | Core open source code (BSL 1.1) |
| `DecisionRecordsORG/ee` | **Private** | Enterprise Edition code |

## Step 1: Create GitHub Organization

1. Go to https://github.com/organizations/plan
2. Select **Free** plan (sufficient for public repos + private repos)
3. Organization name: `DecisionRecordsORG`
4. Contact email: `admin@decisionrecords.org`
5. Organization belongs to: Select "My personal account" or "A business"

### Organization Settings

After creation, configure:

1. **Profile**: Add organization description and avatar
2. **Member privileges**: Set default repository permissions
3. **Security**: Enable 2FA requirement for all members (recommended)

## Step 2: Create Private `ee` Repository

Create the Enterprise Edition repository first (since public repo will reference it):

```bash
# Create the private ee repo
gh repo create DecisionRecordsORG/ee --private --description "Enterprise Edition code for Decision Records"

# Or via GitHub UI:
# 1. Go to https://github.com/organizations/DecisionRecordsORG/repositories/new
# 2. Name: ee
# 3. Visibility: Private
# 4. Initialize with README: No
```

### Push Existing ee/ Content

```bash
# From your current repository, push ee/ to the new private repo
cd /path/to/architecture-decisions/ee
git init
git add .
git commit -m "Initial Enterprise Edition code"
git branch -M main
git remote add origin git@github.com:DecisionRecordsORG/ee.git
git push -u origin main
```

## Step 3: Create Public Repository

Use `.gitignore-public` to create a clean public repo:

```bash
# Create a fresh directory (outside current repo)
mkdir ../DecisionRecords-public
cd ../DecisionRecords-public
git init

# Copy only public files (excludes ee/, .claude/, secrets, etc.)
cd ../architecture-decisions
rsync -av --exclude-from='.gitignore-public' . ../DecisionRecords-public/

# Initialize the public repo
cd ../DecisionRecords-public
git add .
git commit -m "Initial open source release"

# Create the GitHub repo
gh repo create DecisionRecordsORG/DecisionRecords --public \
  --description "Open source Architecture Decision Records (ADR) management platform" \
  --source=. --push
```

## Step 4: Add ee as Git Submodule

In the public repository, add the private ee repo as a submodule:

```bash
cd ../DecisionRecords-public

# Add ee as submodule
git submodule add git@github.com:DecisionRecordsORG/ee.git ee

# Commit the submodule reference
git add .gitmodules ee
git commit -m "Add enterprise edition submodule"
git push
```

### Verify Submodule

```bash
# Check submodule status
git submodule status

# Initialize and update (for fresh clones)
git submodule update --init --recursive
```

## Step 5: Configure Repository Settings

### Public Repository (DecisionRecords)

Go to Settings → General:
- **Default branch**: `main`
- **Features**: Enable Issues, Discussions
- **Pull Requests**: Enable "Allow squash merging", "Automatically delete head branches"

Go to Settings → Branches:
- Add branch protection rule for `main`:
  - Require pull request reviews (1 reviewer)
  - Require status checks to pass
  - Require linear history

Go to Settings → Pages (optional):
- Source: Deploy from a branch (`main`, `/docs` folder)

### Private Repository (ee)

Go to Settings → General:
- **Default branch**: `main`
- **Features**: Disable Issues (use main repo), Disable Projects

Go to Settings → Collaborators:
- Add team members with appropriate roles

## Step 6: Configure CI/CD Secrets

### Required Secrets

Add these secrets to the public repository (Settings → Secrets → Actions):

| Secret | Purpose | How to Get |
|--------|---------|------------|
| `EE_REPO_TOKEN` | Access private ee submodule | Create PAT with `repo` scope |
| `GHCR_TOKEN` | Push to GitHub Container Registry | Use `GITHUB_TOKEN` or create PAT |

### Create Personal Access Token for ee Access

1. Go to https://github.com/settings/tokens/new
2. Note: `EE_REPO_TOKEN for CI`
3. Expiration: No expiration (or set reminder)
4. Scopes: `repo` (full control of private repos)
5. Generate token and add to repository secrets

## Step 7: Set Up GitHub Container Registry

Enable GHCR for the organization:

1. Go to Organization Settings → Packages
2. Enable "Improved container support"

### First Push

The `release.yml` workflow will automatically push to GHCR when you create a tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Images will be available at:
- `ghcr.io/decisionrecordsorg/decisionrecords:latest`
- `ghcr.io/decisionrecordsorg/decisionrecords:1.0.0`

## Step 8: Configure Discussions

Enable GitHub Discussions for community support:

1. Go to Settings → General → Features
2. Enable Discussions
3. Set up categories:
   - **Announcements** (maintainers only)
   - **Q&A** (question-answer format)
   - **Ideas** (feature requests)
   - **Show and tell** (community showcases)

## Step 9: Final Verification

### Test Community Edition Clone

```bash
# Clone without submodule (CE user experience)
git clone https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords
ls ee/  # Should be empty

# Build CE
docker build -f Dockerfile.community -t decisionrecords:community .
docker run -p 3000:8000 decisionrecords:community
# Visit http://localhost:3000
```

### Test Enterprise Edition Clone

```bash
# Clone with submodule (EE user experience)
git clone --recurse-submodules https://github.com/DecisionRecordsORG/DecisionRecords.git
cd DecisionRecords
ls ee/  # Should contain backend/, frontend/, etc.

# Build EE
docker build -f ee/deployment/Dockerfile.production -t decisionrecords:enterprise .
```

## Repository URLs Summary

After setup, your repositories will be at:

| Repository | URL |
|------------|-----|
| Public (CE) | https://github.com/DecisionRecordsORG/DecisionRecords |
| Private (EE) | https://github.com/DecisionRecordsORG/ee |
| Docker Image | ghcr.io/decisionrecordsorg/decisionrecords |
| Documentation | https://github.com/DecisionRecordsORG/DecisionRecords/tree/main/docs |

## Migrating from Private Development Repo

If you have an existing private development repository:

```bash
# Archive the old repo (rename it)
gh repo rename architecture-decisions architecture-decisions-archive --repo your-username/architecture-decisions

# Keep it as reference but don't use for new development
```

All new development should happen in the public `DecisionRecordsORG/DecisionRecords` repo (with private `ee/` submodule for enterprise features).

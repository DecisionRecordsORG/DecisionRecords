# Release Process

This document describes the release process for Decision Records Community Edition.

## Release Flow Overview

```
Developer → GitHub PR → Main Branch → GitHub Release → Docker Image → GHCR
                                           ↓
                                      Changelog
                                           ↓
                                   Self-hosted users
                                   (check for updates)
```

## Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes, database migrations required
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, security patches

Version is stored in `version.py`:
```python
__version__ = "1.15.0"
__build_date__ = "2026-01-09"
```

## Creating a Release

### 1. Prepare the Release

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Bump version (choose one)
./scripts/version-bump.sh patch   # Bug fixes
./scripts/version-bump.sh minor   # New features
./scripts/version-bump.sh major   # Breaking changes

# Commit version bump
git add version.py
git commit -m "Release v1.15.0"
git push origin main
```

### 2. Create GitHub Release

```bash
# Create and push tag
git tag -a v1.15.0 -m "Release v1.15.0"
git push origin v1.15.0
```

Then on GitHub:
1. Go to **Releases** → **Draft a new release**
2. Select the tag you just pushed
3. Title: `v1.15.0`
4. Description: Copy from CHANGELOG.md
5. Click **Publish release**

### 3. Automated Docker Build (GitHub Actions)

When a release is published, GitHub Actions automatically:
1. Builds the Community Edition Docker image
2. Pushes to GitHub Container Registry (ghcr.io)
3. Tags with version and `latest`

## Docker Image Tags

| Tag | Description |
|-----|-------------|
| `latest` | Most recent stable release |
| `v1.15.0` | Specific version |
| `v1.15` | Latest patch for v1.15.x |
| `v1` | Latest minor/patch for v1.x.x |

## Release Checklist

Before releasing:

- [ ] All tests pass (`pytest tests/`)
- [ ] Frontend builds successfully (`cd frontend && npm run build`)
- [ ] Docker image builds locally (`docker build -f Dockerfile.community .`)
- [ ] CHANGELOG.md updated with changes
- [ ] Version bumped in version.py
- [ ] No uncommitted changes
- [ ] Database migrations documented (if any)

## Hotfix Process

For urgent fixes to a released version:

```bash
# Create hotfix branch from tag
git checkout -b hotfix/v1.15.1 v1.15.0

# Make fix, commit
git add .
git commit -m "Fix critical bug"

# Bump patch version
./scripts/version-bump.sh patch

# Merge to main
git checkout main
git merge hotfix/v1.15.1

# Tag and release
git tag -a v1.15.1 -m "Hotfix v1.15.1"
git push origin main --tags
```

## Communication

After release:
1. GitHub Release notes (auto-generated + manual highlights)
2. Update documentation if needed
3. Announce on project discussions/social media

## Self-Hosted Update Notifications

Self-hosted instances can check for updates via:

1. **Version API**: `GET /api/version` returns current version
2. **Update Check**: `GET /api/version/check` compares with latest release
3. **GitHub Releases RSS**: Subscribe to release notifications
4. **Watchtower**: Automatic Docker image updates (optional)

See [Self-Hosting Guide](self-hosting.md) for update instructions.
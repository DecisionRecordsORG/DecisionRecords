#!/bin/bash
#
# Version Bump Script for Architecture Decisions Application
#
# Usage:
#   ./scripts/version-bump.sh patch  # 1.0.0 -> 1.0.1
#   ./scripts/version-bump.sh minor  # 1.0.0 -> 1.1.0
#   ./scripts/version-bump.sh major  # 1.0.0 -> 2.0.0
#   ./scripts/version-bump.sh        # Just update build date
#

set -e

VERSION_FILE="version.py"
BUMP_TYPE="${1:-none}"

# Get current version
CURRENT_VERSION=$(grep -o '__version__ = "[^"]*"' "$VERSION_FILE" | cut -d'"' -f2)

if [ -z "$CURRENT_VERSION" ]; then
    echo "Error: Could not read current version from $VERSION_FILE"
    exit 1
fi

echo "Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR="${VERSION_PARTS[0]}"
MINOR="${VERSION_PARTS[1]}"
PATCH="${VERSION_PARTS[2]}"

# Calculate new version based on bump type
case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    none)
        # No version bump, just update build date
        ;;
    *)
        echo "Usage: $0 [major|minor|patch]"
        echo "  major: Increment major version (breaking changes)"
        echo "  minor: Increment minor version (new features)"
        echo "  patch: Increment patch version (bug fixes)"
        echo "  (no argument): Update build date only"
        exit 1
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
BUILD_DATE=$(date +%Y-%m-%d)

echo "New version: $NEW_VERSION"
echo "Build date: $BUILD_DATE"

# Update version.py
sed -i '' "s/__version__ = \"[^\"]*\"/__version__ = \"$NEW_VERSION\"/" "$VERSION_FILE"
sed -i '' "s/__build_date__ = \"[^\"]*\"/__build_date__ = \"$BUILD_DATE\"/" "$VERSION_FILE"

echo "Updated $VERSION_FILE"

# If we're bumping version (not just build date), stage the file
if [ "$BUMP_TYPE" != "none" ]; then
    git add "$VERSION_FILE"
    echo "Staged $VERSION_FILE for commit"
fi

echo "Done!"

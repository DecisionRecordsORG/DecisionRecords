#!/bin/bash
# Generate prerender-routes.txt from blog posts and static pages
# This ensures all blog posts are pre-rendered for SEO/social sharing

set -e

FRONTEND_DIR="frontend"
ROUTES_FILE="$FRONTEND_DIR/prerender-routes.txt"
BLOG_COMPONENT="$FRONTEND_DIR/src/app/components/blog/blog-post/blog-post.component.ts"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${BLUE}[PRERENDER]${NC} $1"; }
success() { echo -e "${GREEN}[PRERENDER]${NC} $1"; }

log "Generating prerender routes..."

# Start with static pages
cat > "$ROUTES_FILE" << 'EOF'
# Static pages (auto-generated - do not edit manually)
/
/solutions
/about
/faq
/integrations
/terms
/security
/dpa
/sla
/slack-integration

# Blog listing
/blog

# Blog posts (auto-generated from blog-post.component.ts)
EOF

# Extract blog slugs from blog-post.component.ts
# Looks for: slug: 'some-slug-here' or slug: "some-slug-here"
if [ -f "$BLOG_COMPONENT" ]; then
    # Use sed to extract slugs (works on macOS and Linux)
    grep "slug:" "$BLOG_COMPONENT" | sed -n "s/.*slug:[[:space:]]*['\"]\\([^'\"]*\\)['\"].*/\\1/p" | while read -r slug; do
        if [ -n "$slug" ]; then
            echo "/blog/$slug" >> "$ROUTES_FILE"
        fi
    done

    # Count blog posts
    BLOG_COUNT=$(grep -c "slug:" "$BLOG_COMPONENT" 2>/dev/null || echo "0")
    success "Found $BLOG_COUNT blog posts"
else
    log "Warning: Blog component not found at $BLOG_COMPONENT"
fi

# Show generated routes
TOTAL_ROUTES=$(grep -c "^/" "$ROUTES_FILE" || echo "0")
success "Generated $ROUTES_FILE with $TOTAL_ROUTES routes"

# Show the file contents
echo ""
cat "$ROUTES_FILE"
echo ""

#!/usr/bin/env python3
"""
Blog Post Management Script

This script manages blog posts in the database.

Usage:
    # List all blog posts
    python scripts/manage_blog.py list

    # Add a new blog post
    python scripts/manage_blog.py add --slug "my-blog-post" --title "My Blog Post" \
        --excerpt "A brief description" --category "Documentation" --image "/assets/blog/my-image.svg"

    # Seed initial blog posts (run once after migration)
    python scripts/manage_blog.py seed

    # Update a blog post
    python scripts/manage_blog.py update --slug "my-blog-post" --title "Updated Title"

    # Delete a blog post
    python scripts/manage_blog.py delete --slug "my-blog-post"

    # Publish/unpublish a blog post
    python scripts/manage_blog.py publish --slug "my-blog-post"
    python scripts/manage_blog.py unpublish --slug "my-blog-post"
"""

import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, BlogPost


# Initial blog posts to seed (matching existing content)
INITIAL_POSTS = [
    {
        'slug': 'claude-code-integration-with-decision-records',
        'title': 'Claude Code Integration With Decision Records',
        'excerpt': 'Two commands. That\'s all it takes to give Claude Code persistent access to your team\'s architecture decisions. Here\'s the complete setup guide.',
        'author': 'Decision Records',
        'category': 'Technical',
        'read_time': '6 min read',
        'image': '/assets/blog/claude-code-integration.svg',
        'meta_description': 'Learn how to integrate Claude Code with Decision Records to give your AI assistant persistent access to architecture decisions. Complete setup guide with copy-paste commands.',
        'featured': True,
        'publish_date': datetime(2025, 1, 4),
    },
    {
        'slug': 'how-should-teams-document-important-decisions',
        'title': 'How Should Teams Document Important Decisions?',
        'excerpt': 'Most teams make important decisions but lose the context behind them. We all agree documentation matters. But in practice, we want it to be brief and unobtrusive.',
        'author': 'Decision Records',
        'category': 'Documentation',
        'read_time': '5 min read',
        'image': '/assets/blog/documenting-decisions.svg',
        'meta_description': 'Learn how teams can effectively document important decisions without creating overhead.',
        'featured': True,
        'publish_date': datetime(2024, 12, 1),
    },
    {
        'slug': 'how-to-track-decisions-at-a-startup',
        'title': 'How to Track Decisions at a Startup',
        'excerpt': 'Startups make decisions constantly. Pricing changes, product bets, hiring trade-offs, positioning shifts. The assumption is simple: we\'ll remember. That assumption rarely holds.',
        'author': 'Decision Records',
        'category': 'Startups',
        'read_time': '7 min read',
        'image': '/assets/blog/startup-decisions.svg',
        'meta_description': 'Practical guide to tracking decisions at fast-moving startups without slowing down.',
        'featured': False,
        'publish_date': datetime(2024, 12, 15),
    },
    {
        'slug': 'decision-habit-framework-fashion-brands',
        'title': 'A Decision Habit Framework for Fast-Moving Fashion Brands',
        'excerpt': 'Fashion brands are not slow by accident. They are fast by necessity. The risk is not how decisions are made—it is how quickly decision context disappears.',
        'author': 'Decision Records',
        'category': 'Retail',
        'read_time': '5 min read',
        'image': '/assets/blog/fashion-decisions.svg',
        'meta_description': 'A decision documentation framework designed for the fast pace of fashion retail.',
        'featured': False,
        'publish_date': datetime(2024, 12, 20),
    },
]


def list_posts():
    """List all blog posts."""
    with app.app_context():
        posts = BlogPost.query.order_by(BlogPost.publish_date.desc()).all()

        if not posts:
            print("No blog posts found.")
            return

        print(f"\n{'ID':<4} {'Published':<10} {'Featured':<8} {'Category':<15} {'Slug':<45} Title")
        print("-" * 120)

        for post in posts:
            published = "Yes" if post.published else "No"
            featured = "Yes" if post.featured else "No"
            print(f"{post.id:<4} {published:<10} {featured:<8} {post.category:<15} {post.slug:<45} {post.title[:40]}")


def add_post(slug, title, excerpt, category, image=None, author='Decision Records',
             read_time='5 min read', meta_description=None, featured=False, published=True):
    """Add a new blog post."""
    with app.app_context():
        # Check if slug exists
        existing = BlogPost.query.filter_by(slug=slug).first()
        if existing:
            print(f"Error: Blog post with slug '{slug}' already exists.")
            return False

        post = BlogPost(
            slug=slug,
            title=title,
            excerpt=excerpt,
            author=author,
            category=category,
            read_time=read_time,
            image=image,
            meta_description=meta_description or excerpt[:160],
            featured=featured,
            published=published,
            publish_date=datetime.utcnow(),
        )

        db.session.add(post)
        db.session.commit()

        print(f"Created blog post: {title} (slug: {slug})")
        return True


def update_post(slug, **kwargs):
    """Update an existing blog post."""
    with app.app_context():
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            print(f"Error: Blog post with slug '{slug}' not found.")
            return False

        for key, value in kwargs.items():
            if value is not None and hasattr(post, key):
                setattr(post, key, value)

        db.session.commit()
        print(f"Updated blog post: {post.title}")
        return True


def delete_post(slug):
    """Delete a blog post."""
    with app.app_context():
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            print(f"Error: Blog post with slug '{slug}' not found.")
            return False

        title = post.title
        db.session.delete(post)
        db.session.commit()
        print(f"Deleted blog post: {title}")
        return True


def publish_post(slug):
    """Publish a blog post."""
    return update_post(slug, published=True)


def unpublish_post(slug):
    """Unpublish a blog post."""
    return update_post(slug, published=False)


def seed_posts():
    """Seed initial blog posts."""
    with app.app_context():
        created = 0
        skipped = 0

        for post_data in INITIAL_POSTS:
            existing = BlogPost.query.filter_by(slug=post_data['slug']).first()
            if existing:
                print(f"Skipping existing post: {post_data['slug']}")
                skipped += 1
                continue

            post = BlogPost(**post_data)
            db.session.add(post)
            print(f"Created: {post_data['title']}")
            created += 1

        db.session.commit()
        print(f"\nSeeding complete: {created} created, {skipped} skipped")


def main():
    parser = argparse.ArgumentParser(description='Manage blog posts')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List command
    subparsers.add_parser('list', help='List all blog posts')

    # Seed command
    subparsers.add_parser('seed', help='Seed initial blog posts')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new blog post')
    add_parser.add_argument('--slug', required=True, help='URL slug for the post')
    add_parser.add_argument('--title', required=True, help='Post title')
    add_parser.add_argument('--excerpt', required=True, help='Short description')
    add_parser.add_argument('--category', required=True, help='Category (Documentation, Startups, Enterprise, etc.)')
    add_parser.add_argument('--image', help='Image path (e.g., /assets/blog/my-image.svg)')
    add_parser.add_argument('--author', default='Decision Records', help='Author name')
    add_parser.add_argument('--read-time', default='5 min read', help='Estimated read time')
    add_parser.add_argument('--meta-description', help='SEO meta description')
    add_parser.add_argument('--featured', action='store_true', help='Mark as featured post')
    add_parser.add_argument('--unpublished', action='store_true', help='Create as unpublished draft')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update a blog post')
    update_parser.add_argument('--slug', required=True, help='Slug of post to update')
    update_parser.add_argument('--title', help='New title')
    update_parser.add_argument('--excerpt', help='New excerpt')
    update_parser.add_argument('--category', help='New category')
    update_parser.add_argument('--image', help='New image path')
    update_parser.add_argument('--author', help='New author')
    update_parser.add_argument('--read-time', help='New read time')
    update_parser.add_argument('--meta-description', help='New meta description')
    update_parser.add_argument('--featured', action='store_true', help='Mark as featured')
    update_parser.add_argument('--not-featured', action='store_true', help='Remove featured status')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a blog post')
    delete_parser.add_argument('--slug', required=True, help='Slug of post to delete')

    # Publish command
    publish_parser = subparsers.add_parser('publish', help='Publish a blog post')
    publish_parser.add_argument('--slug', required=True, help='Slug of post to publish')

    # Unpublish command
    unpublish_parser = subparsers.add_parser('unpublish', help='Unpublish a blog post')
    unpublish_parser.add_argument('--slug', required=True, help='Slug of post to unpublish')

    args = parser.parse_args()

    if args.command == 'list':
        list_posts()
    elif args.command == 'seed':
        seed_posts()
    elif args.command == 'add':
        add_post(
            slug=args.slug,
            title=args.title,
            excerpt=args.excerpt,
            category=args.category,
            image=args.image,
            author=args.author,
            read_time=getattr(args, 'read_time', '5 min read'),
            meta_description=getattr(args, 'meta_description', None),
            featured=args.featured,
            published=not args.unpublished,
        )
    elif args.command == 'update':
        kwargs = {}
        if args.title:
            kwargs['title'] = args.title
        if args.excerpt:
            kwargs['excerpt'] = args.excerpt
        if args.category:
            kwargs['category'] = args.category
        if args.image:
            kwargs['image'] = args.image
        if args.author:
            kwargs['author'] = args.author
        if hasattr(args, 'read_time') and args.read_time:
            kwargs['read_time'] = args.read_time
        if hasattr(args, 'meta_description') and args.meta_description:
            kwargs['meta_description'] = args.meta_description
        if args.featured:
            kwargs['featured'] = True
        if args.not_featured:
            kwargs['featured'] = False
        update_post(args.slug, **kwargs)
    elif args.command == 'delete':
        delete_post(args.slug)
    elif args.command == 'publish':
        publish_post(args.slug)
    elif args.command == 'unpublish':
        unpublish_post(args.slug)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

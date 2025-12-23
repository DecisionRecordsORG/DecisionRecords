import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { SiteNavComponent } from '../../shared/site-nav/site-nav.component';
import { SiteFooterComponent } from '../../shared/site-footer/site-footer.component';

interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  author: string;
  date: string;
  readTime: string;
  image: string;
  category: string;
}

@Component({
  selector: 'app-blog-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatIconModule,
    SiteNavComponent,
    SiteFooterComponent
  ],
  template: `
    <div class="blog-list-page">
      <app-site-nav [lightTopBackground]="true"></app-site-nav>

      <header class="blog-header">
        <div class="container">
          <h1>Blog</h1>
          <p class="header-subtitle">
            Thinking about decisions, documentation, and organisational memory
          </p>
        </div>
      </header>

      <main class="blog-content">
        <div class="container">
          <div class="posts-grid">
            @for (post of posts; track post.slug) {
              <article class="post-card">
                <a [routerLink]="['/blog', post.slug]" class="post-image-link">
                  <div class="post-image">
                    <img [src]="post.image" [alt]="post.title" />
                  </div>
                </a>
                <div class="post-content">
                  <span class="post-category">{{ post.category }}</span>
                  <h2>
                    <a [routerLink]="['/blog', post.slug]">{{ post.title }}</a>
                  </h2>
                  <p class="post-excerpt">{{ post.excerpt }}</p>
                  <div class="post-meta">
                    <span class="post-author">{{ post.author }}</span>
                    <span class="meta-divider">·</span>
                    <span class="post-date">{{ post.date }}</span>
                    <span class="meta-divider">·</span>
                    <span class="post-read-time">{{ post.readTime }}</span>
                  </div>
                </div>
              </article>
            }
          </div>
        </div>
      </main>

      <app-site-footer></app-site-footer>
    </div>
  `,
  styles: [`
    .blog-list-page {
      min-height: 100vh;
      background: #fff;
      display: flex;
      flex-direction: column;
    }

    .blog-header {
      background: #fafafa;
      border-bottom: 1px solid #eee;
      padding: 100px 24px 48px;
    }

    .container {
      max-width: 900px;
      margin: 0 auto;
    }

    .blog-header h1 {
      font-size: 2.25rem;
      font-weight: 600;
      color: #111;
      margin: 0 0 8px;
      letter-spacing: -0.02em;
    }

    .header-subtitle {
      font-size: 1.1rem;
      color: #666;
      margin: 0;
      line-height: 1.5;
    }

    .blog-content {
      flex: 1;
      padding: 48px 24px;
    }

    .posts-grid {
      display: flex;
      flex-direction: column;
      gap: 48px;
    }

    .post-card {
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 32px;
      align-items: start;
    }

    .post-image-link {
      display: block;
      text-decoration: none;
    }

    .post-image {
      aspect-ratio: 16/10;
      border-radius: 8px;
      overflow: hidden;
      background: #f5f5f5;
    }

    .post-image img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.3s ease;
    }

    .post-card:hover .post-image img {
      transform: scale(1.03);
    }

    .post-content {
      padding: 8px 0;
    }

    .post-category {
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 500;
      color: #2563eb;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }

    .post-content h2 {
      font-size: 1.35rem;
      font-weight: 600;
      line-height: 1.35;
      margin: 0 0 12px;
      letter-spacing: -0.01em;
    }

    .post-content h2 a {
      color: #111;
      text-decoration: none;
      transition: color 0.2s;
    }

    .post-content h2 a:hover {
      color: #2563eb;
    }

    .post-excerpt {
      font-size: 0.95rem;
      color: #555;
      line-height: 1.6;
      margin: 0 0 16px;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .post-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      color: #888;
    }

    .meta-divider {
      color: #ccc;
    }

    @media (max-width: 700px) {
      .blog-header {
        padding: 90px 20px 40px;
      }

      .blog-header h1 {
        font-size: 1.75rem;
      }

      .blog-content {
        padding: 32px 20px;
      }

      .post-card {
        grid-template-columns: 1fr;
        gap: 16px;
      }

      .post-image {
        aspect-ratio: 16/9;
      }

      .post-content h2 {
        font-size: 1.2rem;
      }
    }
  `]
})
export class BlogListComponent {
  posts: BlogPost[] = [
    {
      slug: 'how-should-teams-document-important-decisions',
      title: 'How Should Teams Document Important Decisions?',
      excerpt: 'Most teams make important decisions but lose the context behind them. We all agree documentation matters. But in practice, we want it to be brief and unobtrusive.',
      author: 'Decision Records',
      date: 'December 2024',
      readTime: '5 min read',
      image: '/assets/blog/documenting-decisions.svg',
      category: 'Documentation'
    },
    {
      slug: 'where-do-startup-decisions-go',
      title: 'Where Do Startup Decisions Go When No One Writes Them Down?',
      excerpt: 'Startups make decisions constantly. Pricing changes, product bets, hiring trade-offs, positioning shifts. The assumption is simple: we\'ll remember. That assumption rarely holds.',
      author: 'Decision Records',
      date: 'December 2024',
      readTime: '7 min read',
      image: '/assets/blog/startup-decisions.svg',
      category: 'Startups'
    },
    {
      slug: 'decision-habit-framework-fashion-brands',
      title: 'A Decision Habit Framework for Fast-Moving Fashion Brands',
      excerpt: 'Fashion brands are not slow by accident. They are fast by necessity. The risk is not how decisions are made—it is how quickly decision context disappears.',
      author: 'Decision Records',
      date: 'December 2024',
      readTime: '5 min read',
      image: '/assets/blog/fashion-decisions.svg',
      category: 'Retail'
    }
  ];
}

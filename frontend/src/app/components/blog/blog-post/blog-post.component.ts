import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { Title, Meta } from '@angular/platform-browser';

interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  author: string;
  date: string;
  readTime: string;
  image: string;
  category: string;
  content: string;
  metaDescription: string;
}

interface RelatedPost {
  slug: string;
  title: string;
  excerpt: string;
}

@Component({
  selector: 'app-blog-post',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatIconModule
  ],
  template: `
    <div class="blog-post-page">
      @if (post) {
        <header class="post-header">
          <div class="header-container">
            <a routerLink="/blog" class="back-link">
              <mat-icon>arrow_back</mat-icon>
              <span>All Articles</span>
            </a>
          </div>
          <div class="header-container">
            <span class="post-category">{{ post.category }}</span>
            <h1>{{ post.title }}</h1>
            <div class="post-meta">
              <span class="post-date">{{ post.date }}</span>
              <span class="meta-divider">·</span>
              <span class="post-read-time">{{ post.readTime }}</span>
            </div>
          </div>
        </header>

        <div class="post-body">
          <div class="post-body-container">
            <!-- Author Sidebar -->
            <aside class="author-sidebar">
              <div class="author-card">
                <img src="/assets/lawrence-nyakiso.png" alt="Lawrence Nyakiso" class="author-photo" />
                <h4 class="author-name">Lawrence Nyakiso</h4>
                <p class="author-role">Founder</p>
                <p class="author-bio">
                  Building tools to help teams preserve decision context and why they were made. Previously worked on projects where decisions got lost.
                </p>
              </div>
            </aside>

            <!-- Main Content -->
            <main class="post-main">
              <div class="post-hero-image">
                <img [src]="post.image" [alt]="post.title" />
              </div>

              <article class="post-content">
                <div class="prose" [innerHTML]="post.content"></div>
              </article>
            </main>
          </div>
        </div>

        @if (relatedPosts.length > 0) {
          <section class="related-reading">
            <div class="related-container">
              <h2>Related Reading</h2>
              <div class="related-posts">
                @for (related of relatedPosts; track related.slug) {
                  <a [routerLink]="['/blog', related.slug]" class="related-card">
                    <h3>{{ related.title }}</h3>
                    <p>{{ related.excerpt }}</p>
                    <span class="read-more">Read article →</span>
                  </a>
                }
              </div>
            </div>
          </section>
        }
      } @else {
        <div class="not-found">
          <div class="container">
            <h1>Article Not Found</h1>
            <p>The article you're looking for doesn't exist.</p>
            <a routerLink="/blog" class="back-button">
              <mat-icon>arrow_back</mat-icon>
              Back to Blog
            </a>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .blog-post-page {
      min-height: 100vh;
      background: #fff;
      display: flex;
      flex-direction: column;
    }

    /* Header */
    .post-header {
      background: #fafafa;
      border-bottom: 1px solid #eee;
      padding: 100px 24px 40px;
    }

    .header-container {
      max-width: 1000px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 48px;
    }

    .header-container > * {
      grid-column: 2;
    }

    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #666;
      text-decoration: none;
      font-size: 0.9rem;
      margin-bottom: 20px;
      transition: color 0.2s;
    }

    .back-link:hover {
      color: #2563eb;
    }

    .back-link mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .post-category {
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 500;
      color: #2563eb;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 12px;
    }

    .post-header h1 {
      font-size: 2.25rem;
      font-weight: 600;
      color: #111;
      margin: 0 0 16px;
      letter-spacing: -0.02em;
      line-height: 1.25;
      max-width: 700px;
    }

    .post-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: #666;
    }

    .meta-divider {
      color: #ccc;
    }

    /* Post Body with Sidebar */
    .post-body {
      flex: 1;
      padding: 48px 24px;
    }

    .post-body-container {
      max-width: 1000px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 48px;
      align-items: start;
    }

    /* Author Sidebar */
    .author-sidebar {
      position: sticky;
      top: 100px;
    }

    .author-card {
      text-align: center;
    }

    .author-photo {
      width: 100px;
      height: 100px;
      border-radius: 50%;
      object-fit: cover;
      margin-bottom: 16px;
      border: 3px solid #f1f5f9;
    }

    .author-name {
      font-size: 1rem;
      font-weight: 600;
      color: #111;
      margin: 0 0 4px;
    }

    .author-role {
      font-size: 0.85rem;
      color: #2563eb;
      margin: 0 0 12px;
      font-weight: 500;
    }

    .author-bio {
      font-size: 0.85rem;
      color: #666;
      line-height: 1.5;
      margin: 0;
    }

    /* Main Content */
    .post-main {
      min-width: 0;
    }

    .post-hero-image {
      margin-bottom: 32px;
    }

    .post-hero-image img {
      width: 100%;
      max-height: 400px;
      object-fit: cover;
      border-radius: 8px;
      background: #f5f5f5;
    }

    .post-content {
      max-width: 700px;
    }

    /* Typography - Google Fonts readability research */
    .prose {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      font-size: 1.05rem;
      line-height: 1.7;
      color: #333;
    }

    .prose :first-child {
      margin-top: 0;
    }

    .prose p {
      margin: 0 0 1.5em;
    }

    .prose h2 {
      font-size: 1.4rem;
      font-weight: 600;
      color: #111;
      margin: 2.5em 0 0.75em;
      letter-spacing: -0.01em;
      line-height: 1.3;
    }

    .prose h3 {
      font-size: 1.15rem;
      font-weight: 600;
      color: #222;
      margin: 2em 0 0.6em;
    }

    .prose ul, .prose ol {
      margin: 0 0 1.5em;
      padding-left: 1.5em;
    }

    .prose li {
      margin-bottom: 0.5em;
    }

    .prose blockquote {
      margin: 2em 0;
      padding: 1em 1.5em;
      border-left: 3px solid #2563eb;
      background: #f8fafc;
      font-style: italic;
      color: #555;
    }

    .prose blockquote p:last-child {
      margin-bottom: 0;
    }

    .prose strong {
      font-weight: 600;
      color: #111;
    }

    .prose em {
      font-style: italic;
    }

    .prose a {
      color: #2563eb;
      text-decoration: underline;
      text-underline-offset: 2px;
    }

    .prose a:hover {
      color: #1d4ed8;
    }

    .prose .lead {
      font-size: 1.2rem;
      color: #444;
      line-height: 1.6;
      margin-bottom: 2em;
    }

    /* Related Reading */
    .related-reading {
      background: #f8fafc;
      padding: 60px 24px;
      border-top: 1px solid #eee;
    }

    .related-container {
      max-width: 1000px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 48px;
    }

    .related-container > * {
      grid-column: 2;
    }

    .related-reading h2 {
      font-size: 1.25rem;
      font-weight: 600;
      color: #111;
      margin: 0 0 24px;
    }

    .related-posts {
      display: grid;
      gap: 20px;
    }

    .related-card {
      display: block;
      padding: 24px;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      text-decoration: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    .related-card:hover {
      border-color: #2563eb;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
    }

    .related-card h3 {
      font-size: 1.1rem;
      font-weight: 600;
      color: #111;
      margin: 0 0 8px;
      line-height: 1.35;
    }

    .related-card p {
      font-size: 0.9rem;
      color: #666;
      margin: 0 0 12px;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .read-more {
      font-size: 0.85rem;
      font-weight: 500;
      color: #2563eb;
    }

    /* Not Found */
    .not-found {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 120px 24px;
      text-align: center;
    }

    .container {
      max-width: 700px;
      margin: 0 auto;
    }

    .not-found h1 {
      font-size: 1.5rem;
      color: #111;
      margin: 0 0 8px;
    }

    .not-found p {
      color: #666;
      margin: 0 0 24px;
    }

    .back-button {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 12px 24px;
      background: #111;
      color: #fff;
      text-decoration: none;
      border-radius: 100px;
      font-weight: 500;
      font-size: 0.9rem;
      transition: background 0.2s;
    }

    .back-button:hover {
      background: #333;
    }

    .back-button mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    /* Responsive */
    @media (max-width: 900px) {
      .header-container,
      .related-container {
        display: block; /* Remove grid on smaller screens */
      }

      .post-body-container {
        grid-template-columns: 1fr;
        gap: 32px;
      }

      .author-sidebar {
        position: static;
        order: -1;
      }

      .author-card {
        display: flex;
        align-items: center;
        gap: 16px;
        text-align: left;
        padding: 20px;
        background: #f8fafc;
        border-radius: 12px;
      }

      .author-photo {
        width: 64px;
        height: 64px;
        margin-bottom: 0;
        flex-shrink: 0;
      }

      .author-card > div {
        flex: 1;
      }

      .author-name {
        margin-bottom: 2px;
      }

      .author-role {
        margin-bottom: 8px;
      }
    }

    @media (max-width: 600px) {
      .post-header {
        padding: 90px 20px 32px;
      }

      .post-header h1 {
        font-size: 1.6rem;
      }

      .post-meta {
        flex-wrap: wrap;
      }

      .post-body {
        padding: 32px 20px;
      }

      .author-card {
        flex-direction: column;
        text-align: center;
      }

      .author-photo {
        width: 80px;
        height: 80px;
      }

      .prose {
        font-size: 1rem;
      }

      .prose h2 {
        font-size: 1.25rem;
      }

      .related-reading {
        padding: 40px 20px;
      }
    }
  `]
})
export class BlogPostComponent implements OnInit {
  currentYear = new Date().getFullYear();
  post: BlogPost | null = null;
  relatedPosts: RelatedPost[] = [];

  private posts: BlogPost[] = [
    {
      slug: 'how-should-teams-document-important-decisions',
      title: 'How Should Teams Document Important Decisions?',
      excerpt: 'Most teams make important decisions but lose the context behind them. We all agree documentation matters. But in practice, we want it to be brief and unobtrusive.',
      author: 'Decision Records',
      date: 'November 2025',
      readTime: '5 min read',
      image: '/assets/blog/documenting-decisions.svg',
      category: 'Documentation',
      metaDescription: 'Most teams make important decisions but lose the context behind them. This article explains how teams should document decisions to preserve shared understanding as they grow.',
      content: `
        <p class="lead">Most organisations I have worked with fall into a few familiar categories when it comes to documentation: <em>Do what you want. This is how we document. This is where we document. Just put it in the Google folder.</em></p>

        <p>You probably recognised one—or several—of these.</p>

        <p>We all agree documentation matters. But in practice, we want it to be <strong>brief and unobtrusive</strong>. Unless it is describing a Boeing part. Then suddenly detail, precision, and traceability matter a lot.</p>

        <p>There is no single correct way to document. Different teams and situations require different levels of detail. <strong>The real problem is not how teams document, but what never gets documented at all.</strong></p>

        <h2>Where Decisions Go</h2>

        <p>In most organisations, decisions are made in meetings, chats, calls, and slide decks. They are discussed, agreed on, and then <strong>quietly disappear</strong>.</p>

        <p>Weeks or months later, someone asks:</p>
        <ul>
          <li>Why did we do it this way?</li>
          <li>Why didn't we choose the alternative?</li>
          <li>Was this intentional or just what happened?</li>
        </ul>

        <p>At that point, <strong>the answer usually lives in someone's head</strong>. Or nowhere.</p>

        <p>I have a soft spot for the "put it in the Google folder" approach. It feels fast and flexible. It works—until the <strong>person with the context is unavailable</strong>, or another team needs to understand a decision they were not part of.</p>

        <p>What is missing is not files. <strong>It is shared context.</strong></p>

        <h2>Decisions Are Made. Context Is Lost.</h2>

        <p>What is remarkable is not that decisions are made—it is how rarely they are treated as <strong>first-class organisational assets</strong>.</p>

        <p>Product decisions. Pricing decisions. Hiring decisions. Process decisions. Brand decisions. Tooling decisions.</p>

        <p>These choices shape how an organisation operates, yet <strong>the reasoning behind them is rarely easy to find</strong>. As teams grow, change, or work across functions, the lack of decision context slows communication and creates friction.</p>

        <p>People end up <strong>re-litigating old discussions</strong>, or working around decisions they do not fully understand.</p>

        <h2>What It Means to Document a Decision</h2>

        <p>Documenting a decision does not mean writing a long document. It means <strong>capturing enough context</strong> so that someone else can understand the reasoning later.</p>

        <ul>
          <li><strong>What</strong> decision was made.</li>
          <li><strong>Why</strong> it was made at the time.</li>
          <li>What <strong>alternatives</strong> were considered.</li>
          <li>What <strong>assumptions</strong> existed.</li>
        </ul>

        <p>Nothing more than necessary. Nothing essential missing.</p>

        <p>When decisions are documented this way, <strong>teams communicate more clearly</strong>. Other teams can understand intent without needing a meeting. New people can get context without reverse-engineering the past.</p>

        <h2>Decision Records as Organisational Memory</h2>

        <p>Over time, documented decisions form <strong>a shared memory for the organisation</strong>. They explain not just what exists today, but how and why it came to be.</p>

        <p>This is not about control or governance. It is about <strong>ensuring the next person has context</strong>, and that other teams have easier access to your team's decisions. That is what enables communication and collaboration to scale.</p>

        <p>This line of thinking led to DecisionRecords.org.</p>

        <p>DecisionRecords.org exists to give organisations a simple, shared place to capture important decisions with context, so that <strong>decision memory does not disappear</strong> as teams evolve.</p>

        <p><strong>Not more documentation. Just better memory.</strong></p>
      `
    },
    {
      slug: 'how-to-track-decisions-at-a-startup',
      title: 'How to Track Decisions at a Startup',
      excerpt: 'Startups make decisions constantly. Pricing changes, product bets, hiring trade-offs, positioning shifts. The assumption is simple: we\'ll remember. That assumption rarely holds.',
      author: 'Decision Records',
      date: 'November 2025',
      readTime: '7 min read',
      image: '/assets/blog/startup-decisions.svg',
      category: 'Startups',
      metaDescription: 'Learn how startups can track important decisions without slowing down. A practical guide to lightweight decision records that preserve context and support fast-moving teams.',
      content: `
        <p class="lead">Startups make decisions constantly. That is not a flaw; it is the job.</p>

        <p>Pricing changes, product bets, hiring trade-offs, positioning shifts, tooling choices, process shortcuts. Most of these decisions are made quickly, collaboratively, and <strong>with incomplete information</strong>. At the time, everyone involved understands what was decided and why.</p>

        <p>The assumption is simple: <strong>we'll remember</strong>.</p>

        <p>That assumption rarely holds.</p>

        <h2>Speed Is Not the Enemy</h2>

        <p>Startups often feel a <strong>quiet guilt about documentation</strong>. Compared to larger organisations, they document less, formalise less, and move faster. Founders worry they are being "undisciplined" or "immature".</p>

        <p>This framing is wrong.</p>

        <p>Research on decision-making consistently shows that <strong>speed and bounded rationality are often advantageous</strong> in uncertain environments. Early-stage teams cannot wait for perfect information. They rely on judgment, intuition, and shared context.</p>

        <p><strong>The problem is not speed. The problem is memory decay.</strong></p>

        <h2>Decisions Decay Faster Than Outcomes</h2>

        <p>Psychological research shows that <strong>humans are surprisingly bad at remembering why they made a decision</strong>, even when they remember the decision itself. Over time, people reconstruct reasoning to fit current outcomes. This is known as hindsight bias.</p>

        <p>In startups, this effect is amplified:</p>
        <ul>
          <li>Teams change rapidly</li>
          <li>Roles blur</li>
          <li>Decisions compound</li>
          <li>Context shifts</li>
        </ul>

        <p>Six months later, the team remembers what they chose, but <strong>not the constraints, assumptions, or trade-offs</strong> that shaped the choice. When conditions change, it becomes hard to tell whether a decision should be revisited—or whether it still makes sense.</p>

        <p>This is where many startups stall. Not because they lack data, but because <strong>they lack historical context</strong>.</p>

        <h2>Why "Just Document It" Does Not Work</h2>

        <p>Telling startups to "document more" is unhelpful. It ignores the real constraint: <strong>cognitive and operational load</strong>.</p>

        <p>Heavy documentation fails because:</p>
        <ul>
          <li>It <strong>interrupts flow</strong></li>
          <li>It creates <strong>performative work</strong></li>
          <li>It competes with delivery</li>
          <li>It rarely gets reused</li>
        </ul>

        <p><strong>What matters is not volume. It is selectivity.</strong></p>

        <p>The most effective teams do not document everything. They <strong>document decisions that other people will need to understand later</strong>.</p>

        <p>This distinction is subtle but critical.</p>

        <h2>The Missing Link: Decision Records as a Thinking Tool</h2>

        <p>Decision records sit at an interesting intersection. They are <strong>not documentation in the traditional sense</strong>, and they are not retrospective analysis either.</p>

        <p>At their best, they serve three purposes at once:</p>
        <ol>
          <li>They <strong>slow thinking just enough</strong> to clarify intent</li>
          <li>They <strong>externalise reasoning</strong> so it can survive team changes</li>
          <li>They <strong>reduce future cognitive load</strong> by preventing re-litigation</li>
        </ol>

        <p>This aligns closely with research on decision hygiene. Good decisions are not defined by outcomes alone, but by <strong>whether the reasoning was sound</strong> given the information available at the time.</p>

        <p>Recording that reasoning is not bureaucracy. It is a way of <strong>preserving intellectual honesty</strong>.</p>

        <h2>What Startups Should Actually Record</h2>

        <p>Startups should not record tasks, updates, or routine choices. They should record <strong>decisions that</strong>:</p>
        <ul>
          <li><strong>Shape future options</strong></li>
          <li><strong>Affect multiple teams</strong></li>
          <li>Are likely to be <strong>questioned later</strong></li>
          <li>Were made under <strong>meaningful uncertainty</strong></li>
        </ul>

        <p>Examples are everywhere: choosing a pricing model, deprioritising a market, adopting a tool that affects workflow, deciding not to pursue a partnership.</p>

        <p>If a future teammate might reasonably ask, <strong>"Why did we do it this way?"</strong>, that decision deserves a short record.</p>

        <h2>A Lightweight Habit That Scales</h2>

        <p>The most effective approach is <strong>not a process, but a habit</strong>.</p>

        <p>After an important decision, capture four things:</p>
        <ul>
          <li><strong>What</strong> was decided</li>
          <li><strong>Why</strong> it made sense at the time</li>
          <li>What <strong>alternatives</strong> were considered</li>
          <li>What <strong>assumptions</strong> were in play</li>
        </ul>

        <p><strong>This can be done in minutes.</strong> It does not require approval, formatting, or ceremony.</p>

        <p>Over time, these records form <strong>a narrative of how the startup thinks</strong>. They reveal patterns, values, and trade-offs. They make it easier to change course without erasing the past.</p>

        <h2>Cutting Through the Guilt</h2>

        <p>Startups do not need enterprise-level documentation. They need <strong>continuity of understanding</strong>.</p>

        <p>Decision records offer a middle ground: <strong>enough structure to preserve context, without the overhead that kills momentum</strong>. They respect the reality of fast-moving teams while acknowledging that memory does not scale on its own.</p>

        <p>This is the gap that DecisionRecords.org was built to address: a shared place to capture important decisions with context, so <strong>early speed does not turn into long-term confusion</strong>.</p>

        <p><strong>Not more documentation. Just enough memory to move forward deliberately.</strong></p>
      `
    },
    {
      slug: 'decision-habit-framework-fashion-brands',
      title: 'A Decision Habit Framework for Fast-Moving Fashion Brands',
      excerpt: 'Fashion brands are not slow by accident. They are fast by necessity. The risk is not how decisions are made—it is how quickly decision context disappears.',
      author: 'Decision Records',
      date: 'November 2025',
      readTime: '5 min read',
      image: '/assets/blog/fashion-decisions.svg',
      category: 'Retail',
      metaDescription: 'Fashion brands make decisions under pressure every day. Learn how a lightweight decision habit can preserve context without slowing momentum.',
      content: `
        <p class="lead">Fashion brands are not slow by accident. They are fast by necessity.</p>

        <p>Trend cycles compress, demand signals are noisy, suppliers operate on long lead times, and consumer sentiment shifts faster than planning calendars. Decisions are made daily—often intuitively, often collaboratively, and often under pressure.</p>

        <p>Despite this, fashion brands are frequently judged against operational models borrowed from tech startups or large enterprises. The result is misplaced guilt: <strong>we should document more, systemise more, formalise more</strong>.</p>

        <p>That framing misunderstands the nature of the business.</p>

        <h2>Fashion Is a High-Velocity Decision Environment</h2>

        <p>Research on decision-making under uncertainty shows that in environments with rapid feedback loops and incomplete data, <strong>experienced intuition often outperforms slow analytical processes</strong>. Fashion retail fits this profile closely.</p>

        <p>Merchandising, assortment planning, pricing, and buying decisions rely heavily on tacit knowledge—pattern recognition built over seasons, not spreadsheets alone. Speed and judgment are not weaknesses here; they are competitive advantages.</p>

        <blockquote>
          <p>The risk is not how decisions are made.<br/>The risk is how quickly decision context disappears.</p>
        </blockquote>

        <h2>What Fashion Brands Actually Lose</h2>

        <p>Fashion organisations rarely lose outcomes. They know what sold, what didn't, what was discounted, and what missed the mark.</p>

        <p><strong>What they lose is reasoning.</strong></p>

        <ul>
          <li>Why was this silhouette approved?</li>
          <li>Why did we push this category harder this season?</li>
          <li>Why did we accept higher markdown risk?</li>
          <li>Why did we choose this supplier despite longer lead times?</li>
        </ul>

        <p>As teams rotate, buyers change, designers move on, and regions operate semi-independently, decisions become detached from their original intent. Over time, <strong>the organisation stops learning from itself</strong>.</p>

        <p>This is not a tooling problem. It is a memory problem.</p>

        <h2>The Decision Habit: A Retail-Specific Approach</h2>

        <p>Fashion brands do not need heavy documentation. They need <strong>a repeatable decision habit</strong> that fits into the rhythm of seasonal work.</p>

        <p>The habit is simple: <strong>When a decision materially shapes future options, capture its context while it is still fresh.</strong></p>

        <p>This applies especially to decisions that:</p>
        <ul>
          <li>Lock in inventory or production</li>
          <li>Influence brand positioning</li>
          <li>Set precedent for future seasons</li>
          <li>Affect multiple teams (design, buying, planning, retail)</li>
        </ul>

        <p>The value comes not from precision, but from timing. Cognitive research shows that <strong>decision rationale degrades rapidly</strong> after the fact. Capturing it immediately—even briefly—preserves accuracy and intent.</p>

        <h2>What to Record (and What to Ignore)</h2>

        <p>Fashion brands often avoid documentation because they fear it will become exhaustive. It does not need to.</p>

        <p>A useful decision record in fashion should answer four questions:</p>
        <ul>
          <li><strong>What did we decide?</strong></li>
          <li><strong>Why did it make sense this season?</strong></li>
          <li><strong>What alternatives were on the table?</strong></li>
          <li><strong>What assumptions did we rely on?</strong></li>
        </ul>

        <p>Assumptions are particularly important in fashion. Trend forecasts, climate expectations, consumer sentiment, and supplier reliability are all probabilistic. <strong>Writing them down makes it possible to learn later</strong> whether a decision failed due to execution, changing conditions, or flawed assumptions.</p>

        <p><strong>Do not document routine execution. Do not document taste debates. Document decisions that shape commitment.</strong></p>

        <h2>Why This Improves Speed, Not Slows It</h2>

        <p>There is a persistent myth that reflection reduces agility. In practice, the opposite is often true.</p>

        <p>Teams that externalise decision context reduce future friction. They spend <strong>less time revisiting old debates</strong>, less time justifying past choices, and less time navigating misalignment between regions or functions.</p>

        <p>In retail organisations, this is especially visible during:</p>
        <ul>
          <li>Mid-season trading reviews</li>
          <li>Range resets</li>
          <li>Post-season analysis</li>
          <li>Leadership transitions</li>
        </ul>

        <p>Decision records act as anchors. They make it possible to <strong>move forward without erasing the past</strong>.</p>

        <h2>Institutional Memory Without Enterprise Overhead</h2>

        <p>Many successful fashion brands operate with minimal formal systems and fragmented tooling. That reality is unlikely to change overnight, nor does it need to.</p>

        <p>A decision habit works precisely because it is tool-agnostic. What matters is that <strong>decisions have a consistent, shared home</strong> where context can be retrieved when needed.</p>

        <p>Over time, these records form a narrative of how the brand thinks: how it balances creativity and risk, how it responds to uncertainty, and how it evolves across seasons.</p>

        <p>DecisionRecords.org exists to support this exact need—a lightweight way for organisations like fashion brands to <strong>retain decision memory without importing enterprise bureaucracy</strong>.</p>

        <p>Not to slow decisions down.<br/><strong>But to ensure the organisation can remember why it moved fast.</strong></p>
      `
    }
  ];

  constructor(
    private route: ActivatedRoute,
    private titleService: Title,
    private metaService: Meta
  ) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      const slug = params['slug'];
      this.post = this.posts.find(p => p.slug === slug) || null;

      if (this.post) {
        const postUrl = `https://decisionrecords.org/blog/${this.post.slug}`;
        // Use PNG for og:image (social platforms don't support SVG)
        const ogImageUrl = 'https://decisionrecords.org/assets/og-image-default.png';

        // Basic meta tags
        this.titleService.setTitle(`${this.post.title} | DecisionRecords`);
        this.metaService.updateTag({ name: 'description', content: this.post.metaDescription });
        this.metaService.updateTag({ name: 'author', content: this.post.author });

        // Open Graph tags (Facebook, LinkedIn, etc.) - use attribute selector for property tags
        this.metaService.updateTag({ property: 'og:title', content: this.post.title }, "property='og:title'");
        this.metaService.updateTag({ property: 'og:description', content: this.post.metaDescription }, "property='og:description'");
        this.metaService.updateTag({ property: 'og:image', content: ogImageUrl }, "property='og:image'");
        this.metaService.updateTag({ property: 'og:url', content: postUrl }, "property='og:url'");
        this.metaService.updateTag({ property: 'og:type', content: 'article' }, "property='og:type'");
        this.metaService.updateTag({ property: 'og:site_name', content: 'DecisionRecords' }, "property='og:site_name'");
        this.metaService.updateTag({ property: 'article:published_time', content: this.post.date }, "property='article:published_time'");
        this.metaService.updateTag({ property: 'article:author', content: this.post.author }, "property='article:author'");

        // Twitter Card tags
        this.metaService.updateTag({ name: 'twitter:card', content: 'summary_large_image' }, "name='twitter:card'");
        this.metaService.updateTag({ name: 'twitter:title', content: this.post.title }, "name='twitter:title'");
        this.metaService.updateTag({ name: 'twitter:description', content: this.post.metaDescription }, "name='twitter:description'");
        this.metaService.updateTag({ name: 'twitter:image', content: ogImageUrl }, "name='twitter:image'");

        // Get related posts (all posts except current)
        this.relatedPosts = this.posts
          .filter(p => p.slug !== slug)
          .map(p => ({
            slug: p.slug,
            title: p.title,
            excerpt: p.excerpt
          }));
      }
    });
  }
}

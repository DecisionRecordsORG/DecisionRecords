# Adding New Marketing Pages

This guide explains how to properly add new pages to the marketing website.

## Architecture Overview

The marketing website uses a shared layout managed at the app level:

- **`app.component.ts`** - Controls which navigation and footer to show based on the current route
- **`SiteNavComponent`** - Marketing site navigation (shown on public routes)
- **`SiteFooterComponent`** - Marketing site footer (shown on public routes)
- **`NavbarComponent`** - App navigation for authenticated tenant pages

**Important:** Do NOT import `SiteNavComponent` or `SiteFooterComponent` into individual page components. They are managed globally in `app.component.ts`.

## Steps to Add a New Marketing Page

### 1. Create the Component

Create a new component file at:
```
frontend/src/app/components/<page-name>/<page-name>.component.ts
```

Basic template:
```typescript
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-<page-name>',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="<page-name>-page">
      <!-- Header -->
      <header class="<page-name>-header">
        <div class="container">
          <h1>Page Title</h1>
          <p class="header-subtitle">Subtitle here</p>
        </div>
      </header>

      <!-- Content -->
      <main class="<page-name>-content">
        <div class="container">
          <!-- Page content here -->
        </div>
      </main>
    </div>
  `,
  styles: [`
    .<page-name>-page {
      min-height: 100vh;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
    }

    .<page-name>-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 50%, #1e40af 100%);
      color: white;
      padding: 100px 24px 60px;
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
    }

    .<page-name>-header h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin: 0 0 12px;
    }

    .header-subtitle {
      font-size: 1.15rem;
      color: rgba(255, 255, 255, 0.85);
      margin: 0;
    }

    .<page-name>-content {
      flex: 1;
      padding: 60px 24px;
    }

    @media (max-width: 768px) {
      .<page-name>-header {
        padding: 32px 16px 48px;
      }

      .<page-name>-header h1 {
        font-size: 1.75rem;
      }

      .<page-name>-content {
        padding: 40px 16px;
      }
    }
  `]
})
export class <PageName>Component {}
```

### 2. Add the Route

In `frontend/src/app/app.routes.ts`, add the route:

```typescript
{
  path: '<page-name>',
  loadComponent: () => import('./components/<page-name>/<page-name>.component').then(m => m.<PageName>Component)
},
```

### 3. Register in app.component.ts

Update `app.component.ts` to include the new route in `publicRoutes`:

```typescript
private publicRoutes = [
  '/',
  '/about',
  '/blog',
  '/solutions',
  '/integrations',
  '/faq',
  '/<page-name>',  // Add your new route here
  // ... other routes
];
```

### 4. Configure Navigation Background (if needed)

If your page has a dark hero section (like homepage), add it to `darkBgRoutes`:

```typescript
private darkBgRoutes = ['/', '/integrations/slack', '/<page-name>'];
```

If your page has a light header background (like blog), add it to `lightTopBgRoutes`:

```typescript
private lightTopBgRoutes = ['/blog', '/<page-name>'];
```

### 5. Add to Footer Links (optional)

If the page should appear in the footer, update `site-footer.component.ts`:

```html
<div class="footer-resources-col">
  <h4>Resources</h4>
  <nav class="footer-legal-links">
    <a routerLink="/solutions">Solutions</a>
    <a routerLink="/<page-name>">Page Name</a>
    <!-- ... -->
  </nav>
</div>
```

## Common Mistakes to Avoid

1. **DO NOT** import `SiteNavComponent` or `SiteFooterComponent` in page components
2. **DO NOT** add `<app-site-nav>` or `<app-site-footer>` to page templates
3. **DO** add the route to `publicRoutes` in `app.component.ts`
4. **DO** use the standard header gradient for consistency

## Testing

1. Run `npm run build` to verify compilation
2. Run `npm start` and navigate to your new page
3. Verify navigation and footer appear correctly
4. Test navigation between pages - no twitching should occur

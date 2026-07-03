import { DOCUMENT } from '@angular/common';
import { Inject, Injectable } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { ActivatedRouteSnapshot, NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';

export interface SeoRouteData {
  title?: string;
  description?: string;
  canonicalPath?: string;
  image?: string;
  type?: string;
  robots?: string;
  index?: boolean;
}

const SITE_URL = 'https://decisionrecords.org';
const DEFAULT_TITLE = 'Decision Records - Open Source Architecture Decision Records';
const DEFAULT_DESCRIPTION = 'Decision Records is an open source platform for capturing and preserving the reasoning behind important architecture decisions.';
const DEFAULT_IMAGE = `${SITE_URL}/assets/og-image-default.png`;

@Injectable({
  providedIn: 'root'
})
export class SeoService {
  private initialized = false;

  constructor(
    private router: Router,
    private title: Title,
    private meta: Meta,
    @Inject(DOCUMENT) private document: Document
  ) {}

  init(): void {
    if (this.initialized) {
      return;
    }

    this.initialized = true;
    this.applySeo(this.router.url);

    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd)
    ).subscribe(event => {
      this.applySeo(event.urlAfterRedirects);
    });
  }

  private applySeo(url: string): void {
    const routeData = this.getDeepestRouteData(this.router.routerState.snapshot.root);
    const seo = (routeData['seo'] || {}) as SeoRouteData;
    const path = this.normalizePath(seo.canonicalPath || url);
    const canonicalUrl = `${SITE_URL}${path}`;
    const title = seo.title || DEFAULT_TITLE;
    const description = seo.description || DEFAULT_DESCRIPTION;
    const image = seo.image || DEFAULT_IMAGE;
    const robots = seo.robots || (seo.index ? 'index, follow' : 'noindex, nofollow');
    const type = seo.type || 'website';

    this.title.setTitle(title);
    this.setTag('name', 'description', description);
    this.setTag('name', 'robots', robots);
    this.setCanonical(canonicalUrl);

    this.setTag('property', 'og:type', type);
    this.setTag('property', 'og:url', canonicalUrl);
    this.setTag('property', 'og:title', title);
    this.setTag('property', 'og:description', description);
    this.setTag('property', 'og:image', image);
    this.setTag('property', 'og:site_name', 'Decision Records');
    this.setTag('property', 'og:locale', 'en_US');

    this.setTag('name', 'twitter:card', 'summary_large_image');
    this.setTag('name', 'twitter:url', canonicalUrl);
    this.setTag('name', 'twitter:title', title);
    this.setTag('name', 'twitter:description', description);
    this.setTag('name', 'twitter:image', image);
  }

  private getDeepestRouteData(route: ActivatedRouteSnapshot): Record<string, unknown> {
    let current = route;
    while (current.firstChild) {
      current = current.firstChild;
    }
    return current.data || {};
  }

  private normalizePath(url: string): string {
    const cleanPath = url.split('?')[0].split('#')[0] || '/';
    return cleanPath.startsWith('/') ? cleanPath : `/${cleanPath}`;
  }

  private setTag(attribute: 'name' | 'property', key: string, content: string): void {
    this.meta.updateTag({ [attribute]: key, content });
  }

  private setCanonical(url: string): void {
    let link = this.document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = this.document.createElement('link');
      link.setAttribute('rel', 'canonical');
      this.document.head.appendChild(link);
    }
    link.setAttribute('href', url);
  }
}

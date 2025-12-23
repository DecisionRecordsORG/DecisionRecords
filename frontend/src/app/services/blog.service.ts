import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

export interface BlogPost {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  author: string;
  category: string;
  readTime: string;
  image: string | null;
  metaDescription: string | null;
  metaKeywords: string | null;
  published: boolean;
  featured: boolean;
  publishDate: string;
  publishDateISO: string;
  createdAt: string;
  updatedAt: string;
}

@Injectable({
  providedIn: 'root'
})
export class BlogService {
  private apiUrl = '/api/blog';

  constructor(private http: HttpClient) {}

  /**
   * Get all published blog posts for the blog listing page.
   * Returns posts ordered by featured status, then by publish date.
   */
  getPosts(): Observable<BlogPost[]> {
    return this.http.get<BlogPost[]>(`${this.apiUrl}/posts`).pipe(
      catchError(error => {
        console.error('Failed to load blog posts:', error);
        return of([]);
      })
    );
  }

  /**
   * Get a single blog post by slug.
   */
  getPost(slug: string): Observable<BlogPost | null> {
    return this.http.get<BlogPost>(`${this.apiUrl}/posts/${slug}`).pipe(
      catchError(error => {
        console.error(`Failed to load blog post ${slug}:`, error);
        return of(null);
      })
    );
  }
}

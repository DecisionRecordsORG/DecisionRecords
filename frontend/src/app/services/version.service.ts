import { Inject, Injectable, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Observable, of, BehaviorSubject } from 'rxjs';
import { catchError, tap } from 'rxjs/operators';

export interface VersionInfo {
  version: string;
  build_date: string;
  git_commit: string;
  environment: string;
}

@Injectable({
  providedIn: 'root'
})
export class VersionService {
  private versionSubject = new BehaviorSubject<VersionInfo | null>(null);
  public version$ = this.versionSubject.asObservable();
  private fallbackVersion: VersionInfo = {
    version: '1.0.0',
    build_date: 'unknown',
    git_commit: 'unknown',
    environment: 'unknown'
  };

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) private platformId: object
  ) {
    if (isPlatformBrowser(this.platformId)) {
      this.loadVersion();
    } else {
      this.versionSubject.next(this.fallbackVersion);
    }
  }

  loadVersion(): void {
    if (!isPlatformBrowser(this.platformId)) {
      this.versionSubject.next(this.fallbackVersion);
      return;
    }

    this.http.get<VersionInfo>('/api/version').pipe(
      tap(info => this.versionSubject.next(info)),
      catchError(() => {
        this.versionSubject.next(this.fallbackVersion);
        return of(this.fallbackVersion);
      })
    ).subscribe();
  }

  getVersion(): Observable<VersionInfo> {
    if (!isPlatformBrowser(this.platformId)) {
      return of(this.fallbackVersion);
    }

    return this.http.get<VersionInfo>('/api/version').pipe(
      catchError(() => of(this.fallbackVersion))
    );
  }

  get currentVersion(): VersionInfo | null {
    return this.versionSubject.value;
  }

  get versionString(): string {
    const info = this.versionSubject.value;
    if (!info) return '';
    if (info.git_commit && info.git_commit !== 'unknown') {
      return `v${info.version} (${info.git_commit})`;
    }
    return `v${info.version}`;
  }
}

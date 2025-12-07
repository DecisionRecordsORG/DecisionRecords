import { Injectable } from '@angular/core';
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

  constructor(private http: HttpClient) {
    this.loadVersion();
  }

  loadVersion(): void {
    this.http.get<VersionInfo>('/api/version').pipe(
      tap(info => this.versionSubject.next(info)),
      catchError(() => {
        // Fallback version if API fails
        const fallback: VersionInfo = {
          version: '1.0.0',
          build_date: 'unknown',
          git_commit: 'unknown',
          environment: 'unknown'
        };
        this.versionSubject.next(fallback);
        return of(fallback);
      })
    ).subscribe();
  }

  getVersion(): Observable<VersionInfo> {
    return this.http.get<VersionInfo>('/api/version').pipe(
      catchError(() => of({
        version: '1.0.0',
        build_date: 'unknown',
        git_commit: 'unknown',
        environment: 'unknown'
      }))
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

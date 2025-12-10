import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, tap } from 'rxjs';
import { Space } from '../models/decision.model';

export interface CreateSpaceRequest {
  name: string;
  description?: string;
}

export interface UpdateSpaceRequest {
  name?: string;
  description?: string;
}

@Injectable({
  providedIn: 'root'
})
export class SpaceService {
  private apiUrl = '/api';

  private spacesSubject = new BehaviorSubject<Space[]>([]);
  spaces$ = this.spacesSubject.asObservable();

  constructor(private http: HttpClient) {}

  /**
   * Get all spaces for the current tenant
   */
  getSpaces(): Observable<Space[]> {
    return this.http.get<Space[]>(`${this.apiUrl}/spaces`).pipe(
      tap(spaces => this.spacesSubject.next(spaces))
    );
  }

  /**
   * Get a specific space with decision count
   */
  getSpace(spaceId: number): Observable<Space> {
    return this.http.get<Space>(`${this.apiUrl}/spaces/${spaceId}`);
  }

  /**
   * Create a new space (requires steward or admin)
   */
  createSpace(request: CreateSpaceRequest): Observable<Space> {
    return this.http.post<Space>(`${this.apiUrl}/spaces`, request).pipe(
      tap(newSpace => {
        const current = this.spacesSubject.value;
        this.spacesSubject.next([...current, newSpace]);
      })
    );
  }

  /**
   * Update a space (requires steward or admin)
   */
  updateSpace(spaceId: number, request: UpdateSpaceRequest): Observable<Space> {
    return this.http.put<Space>(`${this.apiUrl}/spaces/${spaceId}`, request).pipe(
      tap(updatedSpace => {
        const current = this.spacesSubject.value;
        const index = current.findIndex(s => s.id === spaceId);
        if (index !== -1) {
          current[index] = updatedSpace;
          this.spacesSubject.next([...current]);
        }
      })
    );
  }

  /**
   * Delete a space (requires admin, cannot delete default)
   */
  deleteSpace(spaceId: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/spaces/${spaceId}`).pipe(
      tap(() => {
        const current = this.spacesSubject.value;
        this.spacesSubject.next(current.filter(s => s.id !== spaceId));
      })
    );
  }

  /**
   * Get decisions in a specific space
   */
  getSpaceDecisions(spaceId: number): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/spaces/${spaceId}/decisions`);
  }

  /**
   * Get spaces for a specific decision
   */
  getDecisionSpaces(decisionId: number): Observable<Space[]> {
    return this.http.get<Space[]>(`${this.apiUrl}/decisions/${decisionId}/spaces`);
  }

  /**
   * Update which spaces a decision belongs to
   */
  updateDecisionSpaces(decisionId: number, spaceIds: number[]): Observable<Space[]> {
    return this.http.put<Space[]>(`${this.apiUrl}/decisions/${decisionId}/spaces`, {
      space_ids: spaceIds
    });
  }

  /**
   * Get the default space for the current tenant
   */
  getDefaultSpace(): Space | undefined {
    return this.spacesSubject.value.find(s => s.is_default);
  }
}

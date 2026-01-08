import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';
import { Decision, DecisionHistory } from '../models/decision.model';

export interface CreateDecisionRequest {
  title: string;
  context: string;
  decision: string;
  status: string;
  consequences: string;
  infrastructure_ids?: number[];
  space_ids?: number[];
}

export interface UpdateDecisionRequest extends Partial<CreateDecisionRequest> {
  change_reason?: string;
}

@Injectable({
  providedIn: 'root'
})
export class DecisionService {
  private apiUrl = '/api/decisions';

  // Subject to notify components when decisions list needs refresh
  private refreshDecisions$ = new Subject<void>();

  // Observable that components can subscribe to
  readonly onRefreshNeeded$ = this.refreshDecisions$.asObservable();

  constructor(private http: HttpClient) {}

  // Call this to notify all subscribers to refresh their decisions list
  notifyRefreshNeeded(): void {
    this.refreshDecisions$.next();
  }

  getDecisions(): Observable<Decision[]> {
    return this.http.get<Decision[]>(this.apiUrl);
  }

  getDecision(id: number): Observable<Decision> {
    return this.http.get<Decision>(`${this.apiUrl}/${id}`);
  }

  createDecision(decision: CreateDecisionRequest): Observable<Decision> {
    return this.http.post<Decision>(this.apiUrl, decision);
  }

  updateDecision(id: number, decision: UpdateDecisionRequest): Observable<Decision> {
    return this.http.put<Decision>(`${this.apiUrl}/${id}`, decision);
  }

  deleteDecision(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  getDecisionHistory(id: number): Observable<DecisionHistory[]> {
    return this.http.get<DecisionHistory[]>(`${this.apiUrl}/${id}/history`);
  }
}

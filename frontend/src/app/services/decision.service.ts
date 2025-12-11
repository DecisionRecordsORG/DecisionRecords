import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
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

  constructor(private http: HttpClient) {}

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

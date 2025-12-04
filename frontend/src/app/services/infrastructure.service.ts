import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ITInfrastructure, InfrastructureType } from '../models/decision.model';

export interface CreateInfrastructureRequest {
  name: string;
  type: InfrastructureType;
  description?: string;
}

export interface UpdateInfrastructureRequest {
  name?: string;
  type?: InfrastructureType;
  description?: string;
}

@Injectable({
  providedIn: 'root'
})
export class InfrastructureService {
  private apiUrl = '/api/infrastructure';

  constructor(private http: HttpClient) {}

  getInfrastructure(): Observable<ITInfrastructure[]> {
    return this.http.get<ITInfrastructure[]>(this.apiUrl);
  }

  getInfrastructureById(id: number): Observable<ITInfrastructure> {
    return this.http.get<ITInfrastructure>(`${this.apiUrl}/${id}`);
  }

  createInfrastructure(data: CreateInfrastructureRequest): Observable<ITInfrastructure> {
    return this.http.post<ITInfrastructure>(this.apiUrl, data);
  }

  updateInfrastructure(id: number, data: UpdateInfrastructureRequest): Observable<ITInfrastructure> {
    return this.http.put<ITInfrastructure>(`${this.apiUrl}/${id}`, data);
  }

  deleteInfrastructure(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  getInfrastructureTypes(): Observable<InfrastructureType[]> {
    return this.http.get<InfrastructureType[]>(`${this.apiUrl}/types`);
  }
}

/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { TerminalsResponse } from '../models/terminal.model';

@Injectable({ providedIn: 'root' })
export class TerminalsService {

  constructor(private http: HttpClient) {}

  list(): Observable<TerminalsResponse> {
    return this.http.get<TerminalsResponse>('/api/terminals');
  }

  /** Emet una petició de discovery. Les respostes les recull el servidor. */
  scan(): Observable<{ sent_to: string[] }> {
    return this.http.post<{ sent_to: string[] }>('/api/discovery/scan', {});
  }

  link(eui64: string, description: string): Observable<unknown> {
    return this.http.post('/api/terminals/link', { eui64, description });
  }

  assign(deviceId: string, portalName: string): Observable<unknown> {
    return this.http.post(`/api/terminals/${deviceId}/assign`, { portal_name: portalName });
  }

  unassign(deviceId: string): Observable<unknown> {
    return this.http.post(`/api/terminals/${deviceId}/unassign`, {});
  }

  /** Ordena l'alliberament: el registre passa a delete_pending. */
  release(deviceId: string): Observable<unknown> {
    return this.http.post(`/api/terminals/${deviceId}/release`, {});
  }

  /** Esborrat manual del registre, sense instrucció al dispositiu. */
  remove(deviceId: string): Observable<unknown> {
    return this.http.delete(`/api/terminals/${deviceId}`);
  }
}

/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AdminUser, TemporaryPasswordResponse, UserRole } from '../models/user.model';

/** API de gestió d'usuaris. Al servidor, tot requereix el perfil d'administrador. */
@Injectable({ providedIn: 'root' })
export class UsersService {

  constructor(private http: HttpClient) {}

  list(): Observable<{ users: AdminUser[] }> {
    return this.http.get<{ users: AdminUser[] }>('/api/users');
  }

  create(username: string, fullName: string, role: UserRole): Observable<TemporaryPasswordResponse> {
    return this.http.post<TemporaryPasswordResponse>('/api/users',
      { username, full_name: fullName, role });
  }

  update(userId: string, fullName: string, role: UserRole): Observable<{ user: AdminUser }> {
    return this.http.put<{ user: AdminUser }>(`/api/users/${userId}`, { full_name: fullName, role });
  }

  resetPassword(userId: string): Observable<TemporaryPasswordResponse> {
    return this.http.post<TemporaryPasswordResponse>(`/api/users/${userId}/reset-password`, {});
  }

  setActive(userId: string, active: boolean): Observable<{ user: AdminUser }> {
    return this.http.post<{ user: AdminUser }>(`/api/users/${userId}/${active ? 'activate' : 'deactivate'}`, {});
  }

  /** Esborra (anonimitza) un usuari desactivat. No es pot desfer. */
  delete(userId: string): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(`/api/users/${userId}`);
  }

  closeSessions(userId: string): Observable<{ user: AdminUser }> {
    return this.http.post<{ user: AdminUser }>(`/api/users/${userId}/close-sessions`, {});
  }
}

/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import { User } from '../models/user.model';

/**
 * Estat de la sessió.
 *
 * El frontend no veu mai el token: viatja en una cookie HttpOnly que gestiona el
 * navegador. Aquí només se sap qui és l'usuari, preguntant-ho al servidor.
 *
 * user():
 *   undefined  encara no s'ha comprovat
 *   null       no hi ha sessió
 *   User       sessió iniciada
 */
@Injectable({ providedIn: 'root' })
export class AuthService {

  readonly user = signal<User | null | undefined>(undefined);

  /** Cert si la sessió s'ha perdut mentre s'estava fent servir (caducada o revocada). */
  readonly sessionExpired = signal(false);

  constructor(private http: HttpClient) {}

  /** Comprova si ja hi ha una sessió oberta, en arrencar l'aplicació. */
  check(): void {
    this.http.get<{ user: User }>('/api/auth/me').subscribe({
      next: (res) => this.user.set(res.user),
      error: () => this.user.set(null)
    });
  }

  login(username: string, password: string): Observable<{ user: User }> {
    return this.http.post<{ user: User }>('/api/auth/login', { username, password }).pipe(
      tap((res) => {
        this.sessionExpired.set(false);
        this.user.set(res.user);
      })
    );
  }

  logout(): void {
    this.http.post('/api/auth/logout', {}).subscribe({
      next: () => this.clear(false),
      error: () => this.clear(false)
    });
  }

  changePassword(currentPassword: string, newPassword: string): Observable<{ user: User }> {
    return this.http.put<{ user: User }>('/api/auth/password',
      { current_password: currentPassword, new_password: newPassword }).pipe(
      tap((res) => this.user.set(res.user))
    );
  }

  setLanguage(language: string): Observable<{ user: User }> {
    return this.http.put<{ user: User }>('/api/auth/me/language', { language }).pipe(
      tap((res) => this.user.set(res.user))
    );
  }

  /** El servidor ha dit que l'usuari ha de canviar la contrasenya: es torna a llegir. */
  refresh(): void {
    this.check();
  }

  /**
   * Sessió perduda. Només es marca com a caducada si hi havia un usuari: en
   * arrencar sense sessió, el 401 és el normal i no s'ha d'avisar de res.
   */
  clear(expired: boolean): void {
    if (expired && this.user()) {
      this.sessionExpired.set(true);
    }
    this.user.set(null);
  }
}

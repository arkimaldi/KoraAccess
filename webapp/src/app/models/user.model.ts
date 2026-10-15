/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

export type UserRole = 'admin' | 'operator';

/** L'usuari connectat, tal com el retorna GET /api/auth/me. */
export interface User {
  user_id: string;
  username: string;
  full_name: string;
  role: UserRole;
  language: string | null;
  must_change_password: boolean;
}

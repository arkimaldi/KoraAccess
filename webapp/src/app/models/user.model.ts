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

/** Un usuari tal com el veu un administrador a la llista. */
export interface AdminUser extends User {
  is_active: boolean;
  created_dts: string | null;
  last_login_dts: string | null;
  active_sessions: number;
}

/** Resposta de crear un usuari o restablir-li la contrasenya. */
export interface TemporaryPasswordResponse {
  user: AdminUser;
  temporary_password: string;
}

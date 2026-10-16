/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { filter, map, take } from 'rxjs';
import { CanActivateFn, Router, Routes } from '@angular/router';

import { AuthService } from './auth/auth.service';
import { TerminalsComponent } from './terminals/terminals.component';
import { UsersComponent } from './users/users.component';
import { ChangePasswordPageComponent } from './auth/change-password-page.component';

/**
 * Només per a administradors. És una comoditat: si un operador escriu /users a
 * mà, el torna a Terminals en lloc de mostrar-li una pantalla buida. La
 * protecció de debò és al servidor, que respon 403.
 *
 * Espera que se sàpiga qui és l'usuari: el router fa la primera navegació en
 * arrencar, abans que torni la comprovació de la sessió. Sense esperar, en
 * recarregar /users un administrador acabaria a Terminals.
 *
 * Sense sessió deixa passar: es mostra el login, i UsersComponent torna a
 * comprovar el perfil quan finalment es crea.
 */
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return toObservable(auth.user).pipe(
    filter((user) => user !== undefined),
    take(1),
    map((user) => (user === null || user.role === 'admin') ? true : router.parseUrl('/terminals'))
  );
};

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'terminals' },
  { path: 'terminals', component: TerminalsComponent },
  { path: 'users', component: UsersComponent, canActivate: [adminGuard] },
  { path: 'password', component: ChangePasswordPageComponent },
  { path: '**', redirectTo: 'terminals' },
];

/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { AuthService } from './auth.service';

/**
 * Capçalera que el servidor exigeix a les peticions que modifiquen dades. Un
 * formulari d'una altra web no la pot afegir: és una defensa contra CSRF, a més
 * de la cookie SameSite=Strict. Ha de coincidir amb CSRF_HEADER del servidor.
 */
const CSRF_HEADER = 'X-Requested-With';
const CSRF_HEADER_VALUE = 'KoraAccess';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const request = req.clone({ setHeaders: { [CSRF_HEADER]: CSRF_HEADER_VALUE } });

  return next(request).pipe(
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse && req.url.startsWith('/api/')) {
        const key = err.error?.message_key;
        // Un 401 del login és una contrasenya incorrecta, no una sessió perduda.
        if (err.status === 401 && !req.url.startsWith('/api/auth/login')) {
          auth.clear(true);
        } else if (err.status === 403 && key === 'MSG_PASSWORD_CHANGE_REQUIRED') {
          auth.refresh();
        }
      }
      return throwError(() => err);
    })
  );
};

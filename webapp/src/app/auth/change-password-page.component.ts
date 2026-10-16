/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { ChangePasswordComponent } from './change-password.component';

/** Canvi voluntari de contrasenya, des del menú de l'avatar. En acabar, torna a Terminals. */
@Component({
  selector: 'kora-change-password-page',
  standalone: true,
  imports: [ChangePasswordComponent],
  template: `<kora-change-password (done)="back()"></kora-change-password>`
})
export class ChangePasswordPageComponent {
  constructor(private router: Router) {}
  back(): void { this.router.navigateByUrl('/terminals'); }
}

/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, OnInit, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';

import { NavbarComponent } from './navbar/navbar.component';
import { LoginComponent } from './auth/login.component';
import { ChangePasswordComponent } from './auth/change-password.component';
import { ModalConfirmComponent } from './shared/modals/modal-confirm.component';
import { ModalPromptComponent } from './shared/modals/modal-prompt.component';
import { AuthService } from './auth/auth.service';
import { LanguageService } from './services/language.service';

/**
 * Sense sessió es mostra el login, i amb un canvi de contrasenya pendent, només
 * aquest. Les pantalles amb rutes només existeixen amb la sessió iniciada.
 */
@Component({
  selector: 'kora-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, TranslateModule, NavbarComponent, LoginComponent,
            ChangePasswordComponent, ModalConfirmComponent, ModalPromptComponent],
  template: `
    <ng-container *ngIf="auth.user() === undefined">
      <div class="d-flex justify-content-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
    </ng-container>

    <div class="kora-public" *ngIf="auth.user() === null">
      <kora-login></kora-login>
    </div>

    <ng-container *ngIf="auth.user() as user">
      <kora-navbar></kora-navbar>
      <main class="container-xl py-4">
        <kora-change-password *ngIf="user.must_change_password" [forced]="true"></kora-change-password>
        <router-outlet *ngIf="!user.must_change_password"></router-outlet>
      </main>
    </ng-container>

    <!-- Modals genèrics, disponibles per a totes les pantalles -->
    <kora-modal-confirm></kora-modal-confirm>
    <kora-modal-prompt></kora-modal-prompt>
  `
})
export class AppComponent implements OnInit {

  constructor(public auth: AuthService, public language: LanguageService) {
    // En iniciar la sessió, l'idioma de l'usuari passa per davant del desat al
    // navegador i del del navegador mateix.
    effect(() => {
      const language = this.auth.user()?.language;
      if (language) {
        this.language.updateLanguage(language);
      }
    });
  }

  ngOnInit(): void {
    this.language.init();
    this.auth.check();
  }
}

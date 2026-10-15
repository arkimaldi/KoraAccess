/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, OnInit, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';

import { TerminalsComponent } from './terminals/terminals.component';
import { LoginComponent } from './auth/login.component';
import { ChangePasswordComponent } from './auth/change-password.component';
import { AuthService } from './auth/auth.service';
import { LanguageService } from './services/language.service';

@Component({
  selector: 'kora-root',
  standalone: true,
  imports: [CommonModule, TranslateModule, TerminalsComponent, LoginComponent, ChangePasswordComponent],
  template: `
    <header class="topbar">
      <h1>KoraAccess</h1>
      <span class="subtitle">{{ 'Access control' | translate }}</span>
      <div class="topbar-right">
        <!-- [selected] a cada opció i no [value] al select: les opcions surten
             d'un *ngFor, i el [value] s'aplicaria abans que existissin. -->
        <select class="lang-select" aria-label="Language" (change)="onLanguage($event)">
          <option *ngFor="let l of language.supportedLanguages" [value]="l"
                  [selected]="l === language.getLanguage()">{{ language.languageNames[l] }}</option>
        </select>
        <ng-container *ngIf="auth.user() as user">
          <span class="user-name">{{ user.full_name || user.username }}</span>
          <button class="topbar-btn" *ngIf="!user.must_change_password"
                  (click)="changingPassword = true">{{ 'Change password' | translate }}</button>
          <button class="topbar-btn" (click)="auth.logout()">{{ 'Log out' | translate }}</button>
        </ng-container>
      </div>
    </header>
    <main>
      <ng-container *ngIf="auth.user() === undefined">
        <div class="app-loading"><div class="spinner" aria-hidden="true"></div></div>
      </ng-container>
      <kora-login *ngIf="auth.user() === null"></kora-login>
      <ng-container *ngIf="auth.user() as user">
        <kora-change-password *ngIf="user.must_change_password" [forced]="true"></kora-change-password>
        <kora-change-password *ngIf="!user.must_change_password && changingPassword"
                              (done)="changingPassword = false"></kora-change-password>
        <kora-terminals *ngIf="!user.must_change_password && !changingPassword"></kora-terminals>
      </ng-container>
    </main>
  `
})
export class AppComponent implements OnInit {

  changingPassword = false;

  constructor(public auth: AuthService, public language: LanguageService) {
    // En iniciar la sessió, l'idioma de l'usuari passa per davant del desat al
    // navegador i del del navegador mateix.
    effect(() => {
      const user = this.auth.user();
      if (user?.language) {
        this.language.updateLanguage(user.language);
      }
      if (!user) {
        this.changingPassword = false;
      }
    });
  }

  ngOnInit(): void {
    this.language.init();
    this.auth.check();
  }

  onLanguage(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.language.updateLanguage(value);
    // Amb sessió, es desa també com a preferència de l'usuari.
    if (this.auth.user()) {
      this.auth.setLanguage(value).subscribe({ error: () => undefined });
    }
  }
}

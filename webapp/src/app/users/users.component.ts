/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Observable, Subject, takeUntil } from 'rxjs';
import { TranslateModule } from '@ngx-translate/core';

import { UsersService } from './users.service';
import { AuthService } from '../auth/auth.service';
import { LanguageService } from '../services/language.service';
import { MessageService } from '../services/message.service';
import { ModalService } from '../services/modal.service';
import { AdminUser, TemporaryPasswordResponse } from '../models/user.model';
import { ApiMessage } from '../models/terminal.model';
import { ModalUserFormComponent, UserFormData } from './modal-user-form.component';
import { ModalTemporaryPasswordComponent } from './modal-temporary-password.component';
import { ModalConfirmComponent, ConfirmModalData } from '../shared/modals/modal-confirm.component';

/** Gestió d'usuaris. Només per a administradors; el servidor ho fa complir. */
@Component({
  selector: 'kora-users',
  standalone: true,
  imports: [CommonModule, TranslateModule, ModalUserFormComponent, ModalTemporaryPasswordComponent],
  templateUrl: './users.component.html',
  styleUrls: ['./users.component.css']
})
export class UsersComponent implements OnInit, OnDestroy {

  users: AdminUser[] = [];
  loading = true;
  error: ApiMessage | null = null;
  private destroy$ = new Subject<void>();

  constructor(private service: UsersService,
              public auth: AuthService,
              public language: LanguageService,
              public messages: MessageService,
              private modals: ModalService,
              private router: Router) {}

  ngOnInit(): void {
    // Segona comprovació, per si s'ha arribat aquí amb l'URL /users des del
    // login: el guard s'avalua abans d'iniciar la sessió i no es torna a avaluar.
    if (this.auth.user()?.role !== 'admin') {
      this.router.navigateByUrl('/terminals');
      return;
    }
    this.load();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  isSelf(u: AdminUser): boolean {
    return u.user_id === this.auth.user()?.user_id;
  }

  load(): void {
    this.service.list().subscribe({
      next: (res) => { this.users = res.users; this.loading = false; },
      error: (err) => { this.loading = false; this.fail(err); }
    });
  }

  // --- accions -------------------------------------------------------
  create(): void {
    this.openForm({}).subscribe((result: TemporaryPasswordResponse | undefined) => {
      if (result) {
        this.load();
        this.showPassword(result);
      }
    });
  }

  edit(u: AdminUser): void {
    this.openForm({ user: u, isSelf: this.isSelf(u) }).subscribe((result) => {
      if (result) {
        this.load();
        // Si s'ha editat a si mateix (el nom), s'actualitza la capçalera.
        if (this.isSelf(u)) { this.auth.refresh(); }
      }
    });
  }

  resetPassword(u: AdminUser): void {
    this.confirm({ titleKey: '_sys_actionResetPassword', textKey: '_sys_confirmResetPassword',
                   params: { username: u.username }, confirmKey: '_sys_actionResetPassword' }, () =>
      this.run(this.service.resetPassword(u.user_id), (res) => this.showPassword(res as TemporaryPasswordResponse)));
  }

  deactivate(u: AdminUser): void {
    this.confirm({ titleKey: '_sys_actionDeactivate', textKey: '_sys_confirmDeactivateUser',
                   params: { username: u.username }, confirmKey: '_sys_actionDeactivate', danger: true }, () =>
      this.run(this.service.setActive(u.user_id, false)));
  }

  activate(u: AdminUser): void {
    this.run(this.service.setActive(u.user_id, true));
  }

  closeSessions(u: AdminUser): void {
    this.confirm({ titleKey: '_sys_actionCloseSessions', textKey: '_sys_confirmCloseSessions',
                   params: { username: u.username }, confirmKey: '_sys_actionCloseSessions' }, () =>
      this.run(this.service.closeSessions(u.user_id)));
  }

  // --- utilitats -----------------------------------------------------
  private openForm(data: UserFormData): Observable<any> {
    return this.modals.openModal(ModalUserFormComponent.modalMe, data).pipe(takeUntil(this.destroy$));
  }

  private showPassword(res: TemporaryPasswordResponse): void {
    this.modals.openModal(ModalTemporaryPasswordComponent.modalMe,
      { username: res.user.username, password: res.temporary_password });
  }

  private confirm(data: ConfirmModalData, onConfirm: () => void): void {
    this.modals.openModal(ModalConfirmComponent.modalMe, data)
      .pipe(takeUntil(this.destroy$))
      .subscribe((ok) => { if (ok) { onConfirm(); } });
  }

  private run(request: Observable<unknown>, after?: (res: unknown) => void): void {
    this.error = null;
    request.subscribe({
      next: (res) => { this.load(); after?.(res); },
      error: (err) => this.fail(err)
    });
  }

  private fail(err: unknown): void {
    this.error = this.messages.fromHttpError(err);
  }

  trackById(_: number, u: AdminUser): string { return u.user_id; }
}

/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';
import { TranslateModule } from '@ngx-translate/core';

import { ModalBase } from '../shared/modals/modal-base';
import { ModalService } from '../services/modal.service';
import { MessageService } from '../services/message.service';
import { UsersService } from './users.service';
import { AdminUser, UserRole } from '../models/user.model';
import { ApiMessage } from '../models/terminal.model';
import { AutofocusDirective } from '../shared/autofocus.directive';

export interface UserFormData {
  /** Si hi és, s'edita aquest usuari; si no, se'n crea un de nou. */
  user?: AdminUser;
  /** Cert si l'usuari editat és el connectat: no es pot canviar el perfil a si mateix. */
  isSelf?: boolean;
}

/**
 * Crear o editar un usuari. Les mateixes regles que aquí s'avisen es fan
 * complir al servidor (server/app/mgr_auth.py).
 */
@Component({
  selector: 'kora-modal-user-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, TranslateModule, AutofocusDirective],
  templateUrl: './modal-user-form.component.html'
})
export class ModalUserFormComponent extends ModalBase {

  static readonly modalMe = 'kora-modal-user-form';
  protected readonly modalName = ModalUserFormComponent.modalMe;

  readonly roles: UserRole[] = ['operator', 'admin'];
  data: UserFormData = {};
  busy = false;
  error: ApiMessage | null = null;

  form = new FormGroup({
    // Les mateixes condicions que USERNAME_RE al servidor.
    username: new FormControl('', { nonNullable: true, validators: [
      Validators.required, Validators.minLength(2), Validators.maxLength(64),
      Validators.pattern(/^[A-Za-z0-9._-]+$/)] }),
    full_name: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(120)] }),
    role: new FormControl<UserRole>('operator', { nonNullable: true }),
  });

  constructor(modalService: ModalService, private users: UsersService,
              public messages: MessageService) {
    super(modalService);
  }

  get isEdit(): boolean { return !!this.data.user; }

  protected onOpen(data: UserFormData): void {
    this.data = data || {};
    this.error = null;
    this.busy = false;
    const u = this.data.user;
    this.form.reset({ username: u?.username ?? '', full_name: u?.full_name ?? '', role: u?.role ?? 'operator' });
    // El nom d'usuari no es pot canviar: és amb el que s'entra.
    if (this.isEdit) { this.form.controls.username.disable(); } else { this.form.controls.username.enable(); }
    if (this.data.isSelf) { this.form.controls.role.disable(); } else { this.form.controls.role.enable(); }
  }

  submit(): void {
    if (this.busy || this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const request: Observable<unknown> = this.isEdit
      ? this.users.update(this.data.user!.user_id, v.full_name.trim(), v.role)
      : this.users.create(v.username.trim().toLowerCase(), v.full_name.trim(), v.role);
    this.busy = true;
    this.error = null;
    request.subscribe({
      next: (result) => { this.busy = false; this.accept(result); },
      error: (err) => { this.busy = false; this.error = this.messages.fromHttpError(err); }
    });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.modalIsVisible && !this.busy) { this.cancel(); }
  }
}

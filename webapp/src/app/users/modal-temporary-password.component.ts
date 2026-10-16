/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';

import { ModalBase } from '../shared/modals/modal-base';
import { ModalService } from '../services/modal.service';

export interface TemporaryPasswordData {
  username: string;
  password: string;
}

/**
 * Mostra una contrasenya temporal una sola vegada. No es pot tornar a consultar:
 * el servidor només en desa el hash. No es tanca fent clic a fora ni amb
 * Escape, perquè no es perdi per accident.
 */
@Component({
  selector: 'kora-modal-temporary-password',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  template: `
    <div class="modal-overlay" *ngIf="modalIsVisible">
      <div class="modal-content kora-modal" (click)="preventClose($event)" role="dialog" aria-modal="true">
        <div class="modal-header"><h5 class="modal-title">{{ 'Temporary password' | translate }}</h5></div>
        <div class="modal-body">
          <p>{{ '_sys_temporaryPasswordFor' | translate: { username: data.username } }}</p>
          <div class="input-group mb-3">
            <input #passwordInput class="form-control font-monospace temp-password" type="text" readonly
                   [value]="data.password" (focus)="passwordInput.select()">
            <button class="btn btn-outline-primary" type="button" data-copy (click)="copy()">
              <ng-container *ngIf="!copied">{{ 'Copy' | translate }}</ng-container>
              <ng-container *ngIf="copied">{{ 'Copied' | translate }}</ng-container>
            </button>
          </div>
          <div class="alert alert-warning py-2 mb-0">
            {{ 'This password will not be shown again. Give it to the user now: they will have to change it when signing in.' | translate }}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-primary" data-modal-confirm (click)="accept(true)">{{ 'Done' | translate }}</button>
        </div>
      </div>
    </div>
  `
})
export class ModalTemporaryPasswordComponent extends ModalBase {

  static readonly modalMe = 'kora-modal-temporary-password';
  protected readonly modalName = ModalTemporaryPasswordComponent.modalMe;
  data: TemporaryPasswordData = { username: '', password: '' };
  copied = false;

  @ViewChild('passwordInput') passwordInput?: ElementRef<HTMLInputElement>;

  constructor(modalService: ModalService) { super(modalService); }

  protected onOpen(data: TemporaryPasswordData): void {
    this.data = data;
    this.copied = false;
  }

  /**
   * L'API del porta-retalls només funciona en context segur (HTTPS o localhost).
   * En desenvolupament, que va per HTTP i IP, es recorre al mètode antic.
   */
  copy(): void {
    const done = () => { this.copied = true; };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(this.data.password).then(done, () => this.legacyCopy(done));
    } else {
      this.legacyCopy(done);
    }
  }

  private legacyCopy(done: () => void): void {
    const input = this.passwordInput?.nativeElement;
    if (!input) { return; }
    input.select();
    try {
      if (document.execCommand('copy')) { done(); }
    } catch {
      // Si no es pot copiar, la contrasenya queda seleccionada per copiar-la a mà.
    }
  }
}

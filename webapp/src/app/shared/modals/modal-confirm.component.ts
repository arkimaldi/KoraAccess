/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';

import { ModalBase } from './modal-base';
import { ModalService } from '../../services/modal.service';

export interface ConfirmModalData {
  /**
   * Claus de traducció. Com que es passen des del codi i ngx-extract no les
   * troba, han de ser claus _sys_ (convenció de la casa).
   */
  titleKey: string;
  textKey: string;
  params?: Record<string, unknown>;
  confirmKey?: string;
  danger?: boolean;
}

/** Confirmació genèrica. Substitueix window.confirm. Resultat: true si s'accepta. */
@Component({
  selector: 'kora-modal-confirm',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  template: `
    <div class="modal-overlay" *ngIf="modalIsVisible" (click)="cancel()">
      <div class="modal-content kora-modal" (click)="preventClose($event)" role="dialog" aria-modal="true">
        <div class="modal-header"><h5 class="modal-title">{{ data.titleKey | translate: data.params }}</h5></div>
        <div class="modal-body"><p class="mb-0">{{ data.textKey | translate: data.params }}</p></div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" (click)="cancel()">{{ 'Cancel' | translate }}</button>
          <button type="button" class="btn" [class.btn-danger]="data.danger" [class.btn-primary]="!data.danger"
                  data-modal-confirm (click)="accept(true)">{{ (data.confirmKey || '_sys_confirm') | translate }}</button>
        </div>
      </div>
    </div>
  `
})
export class ModalConfirmComponent extends ModalBase {

  static readonly modalMe = 'kora-modal-confirm';
  protected readonly modalName = ModalConfirmComponent.modalMe;
  data: ConfirmModalData = { titleKey: '', textKey: '' };

  constructor(modalService: ModalService) { super(modalService); }

  protected onOpen(data: ConfirmModalData): void {
    this.data = data;
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.modalIsVisible) { this.cancel(); }
  }
}

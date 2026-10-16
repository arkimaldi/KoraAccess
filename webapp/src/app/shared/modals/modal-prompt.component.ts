/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';

import { ModalBase } from './modal-base';
import { ModalService } from '../../services/modal.service';
import { AutofocusDirective } from '../autofocus.directive';

/** Claus _sys_: es passen des del codi i ngx-extract no les troba. */
export interface PromptModalData {
  titleKey: string;
  labelKey: string;
  value?: string;
  maxLength?: number;
  params?: Record<string, unknown>;
}

/** Demana un valor de text. Substitueix window.prompt. Resultat: el text, que pot ser buit. */
@Component({
  selector: 'kora-modal-prompt',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule, AutofocusDirective],
  template: `
    <div class="modal-overlay" *ngIf="modalIsVisible" (click)="cancel()">
      <div class="modal-content kora-modal" (click)="preventClose($event)" role="dialog" aria-modal="true">
        <form (ngSubmit)="accept(value)">
          <div class="modal-header"><h5 class="modal-title">{{ data.titleKey | translate: data.params }}</h5></div>
          <div class="modal-body">
            <label class="form-label" for="modal-prompt-input">{{ data.labelKey | translate }}</label>
            <input id="modal-prompt-input" name="value" class="form-control" type="text"
                   koraAutofocus [(ngModel)]="value" [attr.maxlength]="data.maxLength || null">
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" (click)="cancel()">{{ 'Cancel' | translate }}</button>
            <button type="submit" class="btn btn-primary" data-modal-confirm>{{ '_sys_confirm' | translate }}</button>
          </div>
        </form>
      </div>
    </div>
  `
})
export class ModalPromptComponent extends ModalBase {

  static readonly modalMe = 'kora-modal-prompt';
  protected readonly modalName = ModalPromptComponent.modalMe;
  data: PromptModalData = { titleKey: '', labelKey: '' };
  value = '';

  constructor(modalService: ModalService) { super(modalService); }

  protected onOpen(data: PromptModalData): void {
    this.data = data;
    this.value = data.value ?? '';
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.modalIsVisible) { this.cancel(); }
  }
}

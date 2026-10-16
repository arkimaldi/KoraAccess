/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Directive, OnDestroy, OnInit } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';

import { ModalService, ParsedModalStateType } from '../../services/modal.service';

/**
 * Base dels modals, seguint el patró del ModalService de KapriCloudWebManager:
 * el component es declara a la plantilla i escolta l'estat del servei per
 * saber quan s'obre i quan es tanca.
 *
 * Els resultats segueixen la convenció del servei: undefined vol dir
 * cancel·lat; qualsevol altre valor, acceptat.
 */
@Directive()
export abstract class ModalBase implements OnInit, OnDestroy {

  modalIsVisible = false;
  protected destroy$ = new Subject<void>();

  /** Nom del modal al ModalService. */
  protected abstract readonly modalName: string;

  constructor(protected modalService: ModalService) {}

  ngOnInit(): void {
    this.modalService.getModalState()
      .pipe(takeUntil(this.destroy$))
      .subscribe((state) => {
        const parsed: ParsedModalStateType = this.modalService.parseModalState(this.modalName, state);
        this.modalIsVisible = parsed.isVisible;
        if (parsed.isOnOpen) {
          this.onOpen(state.data);
        }
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  protected abstract onOpen(data: any): void;

  cancel(): void {
    this.modalService.closeModal();
  }

  accept(result: unknown): void {
    this.modalService.closeModal(result ?? null);
  }

  preventClose(event: MouseEvent): void {
    event.stopPropagation();
  }
}

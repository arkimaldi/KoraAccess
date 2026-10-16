/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription, timer } from 'rxjs';
import { TranslateModule } from '@ngx-translate/core';

import { TerminalsService } from '../services/terminals.service';
import { ApiMessage, LicenseInfo, Terminal } from '../models/terminal.model';
import { MessageService } from '../services/message.service';
import { ModalService } from '../services/modal.service';
import { ModalConfirmComponent, ConfirmModalData } from '../shared/modals/modal-confirm.component';
import { ModalPromptComponent, PromptModalData } from '../shared/modals/modal-prompt.component';
import { AutofocusDirective } from '../shared/autofocus.directive';

/**
 * Ritme normal: el discovery s'emet cada 30 s, només mentre la pantalla és
 * oberta.
 */
const REFRESH_PERIOD_MS = 30000;

/**
 * Ritme ràpid mentre hi ha alguna operació en curs (enroll_pending o
 * delete_pending). Només es refresca el llistat, que és una lectura local
 * barata; el discovery segueix el seu ritme normal, perquè és broadcast a tota
 * la xarxa del client i el canvi que esperem no ve d'ell sinó de la BBDD.
 */
const FAST_REFRESH_PERIOD_MS = 5000;

/** Estats que indiquen que hi ha una operació en curs. */
const PENDING_STATUS = ['enroll_pending', 'delete_pending'];

/**
 * Espera entre el primer scan i el primer llistat en entrar a la pantalla.
 * L'scan no espera respostes: sense aquesta pausa, el primer llistat no veuria
 * cap dispositiu verge i la pantalla apareixeria buida.
 */
const INITIAL_SCAN_WAIT_MS = 2000;

@Component({
  selector: 'kora-terminals',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule, AutofocusDirective],
  templateUrl: './terminals.component.html',
  styleUrls: ['./terminals.component.css']
})
export class TerminalsComponent implements OnInit, OnDestroy {

  terminals: Terminal[] = [];
  license: LicenseInfo = { assigned: 0, limit: 0 };
  serverUrl = '';
  loading = false;

  /**
   * Error a mostrar. Es desa el missatge sencer i no el text, perquè es torni a
   * traduir si l'usuari canvia d'idioma mentre és a la pantalla.
   */
  error: ApiMessage | null = null;

  /** Cert fins que arriba el primer llistat amb dades vàlides. */
  initialLoading = true;

  /** device_id de la fila que s'està editant, o null. */
  editingId: string | null = null;

  /** Cert mentre hi ha un modal d'aquesta pantalla obert. */
  private modalOpen = false;
  editValue = '';

  private listTimer?: Subscription;
  private scanTimer?: Subscription;
  private lastScanAt = 0;

  constructor(private service: TerminalsService,
              public messages: MessageService,
              private modals: ModalService) {}

  ngOnInit(): void {
    this.initialLoad();
  }

  /**
   * Primera càrrega: scan, pausa perquè els dispositius responguin, i llavors
   * el primer llistat. Després, el ritme normal.
   */
  private initialLoad(): void {
    this.initialLoading = true;
    this.lastScanAt = Date.now();
    const afterScan = () => {
      this.listTimer = timer(INITIAL_SCAN_WAIT_MS).subscribe(() => this.refresh(false));
    };
    this.service.scan().subscribe({ next: afterScan, error: afterScan });
  }

  ngOnDestroy(): void {
    // En sortir de la pantalla s'atura tot: no s'emet broadcast de manera
    // permanent.
    this.listTimer?.unsubscribe();
    this.scanTimer?.unsubscribe();
  }

  /** Hi ha alguna vinculació o alliberament a mig fer. */
  get hasPendingWork(): boolean {
    return this.terminals.some(t => !!t.status && PENDING_STATUS.includes(t.status));
  }

  /**
   * Reprograma el proper refresc segons si hi ha feina pendent. Es fa amb
   * timer() en lloc d'interval() perquè el període pot canviar a cada cicle.
   */
  private scheduleNext(): void {
    this.listTimer?.unsubscribe();
    const period = this.hasPendingWork ? FAST_REFRESH_PERIOD_MS : REFRESH_PERIOD_MS;
    this.listTimer = timer(period).subscribe(() => {
      // Mentre s'edita una descripció no es refresca: el valor de la base de
      // dades sobreescriuria el que l'usuari està escrivint.
      if (this.editingId !== null || this.modalOpen) {
        this.scheduleNext();
        return;
      }
      // El discovery manté el seu ritme encara que el llistat vagi més ràpid.
      const withScan = Date.now() - this.lastScanAt >= REFRESH_PERIOD_MS;
      this.refresh(withScan);
    });
  }

  refresh(withScan = false): void {
    this.loading = true;
    const load = () => this.service.list().subscribe({
      next: (res) => {
        this.terminals = res.terminals;
        this.license = res.license;
        this.serverUrl = res.server_url;
        this.loading = false;
        this.initialLoading = false;
        this.scheduleNext();
      },
      error: (err) => {
        this.fail(err);
        this.initialLoading = false;
        this.scheduleNext();
      }
    });

    if (withScan) {
      this.lastScanAt = Date.now();
      this.service.scan().subscribe({ next: () => load(), error: () => load() });
    } else {
      load();
    }
  }

  // --- edició de la descripció ---------------------------------------
  /**
   * Cert només per a la fila que s'està editant.
   *
   * No es pot comparar directament editingId === t.device_id: fora d'edició
   * editingId val null, i les files sense registre (FREE, FOREIGN) també tenen
   * device_id a null. La comparació seria certa per a totes elles i entrarien
   * en edició alhora, compartint el mateix camp.
   */
  isEditing(t: Terminal): boolean {
    return this.editingId !== null && t.device_id !== null && this.editingId === t.device_id;
  }

  startEdit(t: Terminal): void {
    if (!t.can_edit_description || !t.device_id) { return; }
    this.editingId = t.device_id;
    this.editValue = t.description || '';
  }

  /** Enter: desa. És l'únic camí per desar. */
  saveEdit(): void {
    if (this.editingId === null) { return; }
    const deviceId = this.editingId;
    const value = this.editValue;
    // Es tanca l'edició abans de desar: quan el camp desaparegui i perdi el
    // focus, cancelEdit() ja no hi trobarà res a cancel·lar.
    this.editingId = null;
    this.run(this.service.updateDescription(deviceId, value));
  }

  /** Escape o perdre el focus: cancel·la sense desar. */
  cancelEdit(): void {
    this.editingId = null;
    this.editValue = '';
  }

  onEditKey(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.saveEdit();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelEdit();
    }
  }

  // --- accions ------------------------------------------------------
  link(t: Terminal): void {
    this.prompt({ titleKey: '_sys_actionLink', labelKey: '_sys_terminalDescription', value: t.description || '',
                  maxLength: 120 }, (description) => this.run(this.service.link(t.eui64, description)));
  }

  assign(t: Terminal): void {
    if (!t.device_id) { return; }
    const deviceId = t.device_id;
    this.prompt({ titleKey: '_sys_actionAssignToDoor', labelKey: '_sys_doorName', maxLength: 120 },
                (portal) => this.run(this.service.assign(deviceId, portal)));
  }

  unassign(t: Terminal): void {
    if (!t.device_id) { return; }
    this.run(this.service.unassign(t.device_id));
  }

  release(t: Terminal): void {
    if (!t.device_id) { return; }
    const deviceId = t.device_id;
    this.confirm({ titleKey: '_sys_actionRelease', textKey: '_sys_confirmRelease', params: { eui64: t.eui64 },
                   confirmKey: '_sys_actionRelease', danger: true },
                 () => this.run(this.service.release(deviceId)));
  }

  remove(t: Terminal): void {
    if (!t.device_id) { return; }
    const deviceId = t.device_id;
    this.confirm({ titleKey: '_sys_actionDeleteRecord', textKey: '_sys_confirmDeleteRecord', params: { eui64: t.eui64 },
                   confirmKey: '_sys_actionDeleteRecord', danger: true },
                 () => this.run(this.service.remove(deviceId)));
  }

  /**
   * Mentre hi ha un modal obert, el polling es comporta com en edició: no
   * refresca, perquè la fila sobre la qual s'actua no canviï per sota.
   */
  private prompt(data: PromptModalData, onAccept: (value: string) => void): void {
    this.modalOpen = true;
    this.modals.openModal(ModalPromptComponent.modalMe, data).subscribe((value) => {
      this.modalOpen = false;
      if (value !== undefined) { onAccept((value ?? '') as string); }
    });
  }

  private confirm(data: ConfirmModalData, onAccept: () => void): void {
    this.modalOpen = true;
    this.modals.openModal(ModalConfirmComponent.modalMe, data).subscribe((ok) => {
      this.modalOpen = false;
      if (ok) { onAccept(); }
    });
  }

  // --- presentació --------------------------------------------------
  private static readonly LABEL_CLASS: Record<string, string> = {
    FREE: 'text-bg-success', LINKED: 'text-bg-warning', ENROLLED: 'text-bg-primary',
    ASSIGNED: 'text-bg-info', FOREIGN: 'text-bg-secondary', DELETE_PENDING: 'text-bg-danger',
  };

  labelClass(t: Terminal): string {
    return `badge label-${t.label.toLowerCase()} ${TerminalsComponent.LABEL_CLASS[t.label] ?? 'text-bg-light'}`;
  }

  private static readonly LINK_CLASS: Record<string, string> = {
    online: 'text-success', lost: 'text-warning-emphasis', severe_lost: 'text-danger fw-semibold',
    offline: 'text-secondary',
  };

  linkClass(t: Terminal): string {
    return t.link ? (TerminalsComponent.LINK_CLASS[t.link] ?? '') : 'text-body-tertiary';
  }

  /** Clau de traducció de l'estat de connexió. */
  linkKey(t: Terminal): string {
    return t.link ? `_sys_link_${t.link}` : '';
  }

  trackByEui64(_: number, t: Terminal): string {
    return t.eui64;
  }

  private run(obs: { subscribe: Function }): void {
    this.loading = true;
    this.error = null;
    (obs as any).subscribe({
      next: () => this.refresh(false),
      error: (err: any) => this.fail(err)
    });
  }

  private fail(err: unknown): void {
    this.loading = false;
    this.error = this.messages.fromHttpError(err);
  }
}

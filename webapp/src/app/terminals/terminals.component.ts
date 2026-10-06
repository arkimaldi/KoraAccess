/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription, timer } from 'rxjs';

import { TerminalsService } from '../services/terminals.service';
import { LicenseInfo, Terminal } from '../models/terminal.model';

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

@Component({
  selector: 'kora-terminals',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './terminals.component.html',
  styleUrls: ['./terminals.component.css']
})
export class TerminalsComponent implements OnInit, OnDestroy {

  terminals: Terminal[] = [];
  license: LicenseInfo = { assigned: 0, limit: 0 };
  serverUrl = '';
  loading = false;
  errorMessage = '';

  private listTimer?: Subscription;
  private scanTimer?: Subscription;
  private lastScanAt = 0;

  constructor(private service: TerminalsService) {}

  ngOnInit(): void {
    this.refresh(true);
    this.scheduleNext();
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
        this.scheduleNext();
      },
      error: (err) => {
        this.fail(err);
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

  // --- accions ------------------------------------------------------
  link(t: Terminal): void {
    const description = window.prompt('Descripció del terminal:', t.description || '');
    if (description === null) { return; }
    this.run(this.service.link(t.eui64, description));
  }

  assign(t: Terminal): void {
    if (!t.device_id) { return; }
    const portal = window.prompt('Nom de la porta:', '');
    if (portal === null) { return; }
    this.run(this.service.assign(t.device_id, portal));
  }

  unassign(t: Terminal): void {
    if (!t.device_id) { return; }
    this.run(this.service.unassign(t.device_id));
  }

  release(t: Terminal): void {
    if (!t.device_id) { return; }
    if (!window.confirm(`Alliberar ${t.eui64}? El terminal quedarà verge.`)) { return; }
    this.run(this.service.release(t.device_id));
  }

  remove(t: Terminal): void {
    if (!t.device_id) { return; }
    if (!window.confirm(`Esborrar el registre de ${t.eui64}?`)) { return; }
    this.run(this.service.remove(t.device_id));
  }

  // --- presentació --------------------------------------------------
  labelClass(t: Terminal): string {
    return 'badge badge-' + t.label.toLowerCase();
  }

  linkClass(t: Terminal): string {
    return t.link ? 'link link-' + t.link : 'link link-unknown';
  }

  linkText(t: Terminal): string {
    switch (t.link) {
      case 'online': return 'En línia';
      case 'lost': return 'Perdut';
      case 'severe_lost': return 'Perdut (greu)';
      case 'offline': return 'Fora de línia';
      default: return '—';
    }
  }

  trackByEui64(_: number, t: Terminal): string {
    return t.eui64;
  }

  private run(obs: { subscribe: Function }): void {
    this.loading = true;
    this.errorMessage = '';
    (obs as any).subscribe({
      next: () => this.refresh(false),
      error: (err: any) => this.fail(err)
    });
  }

  private fail(err: any): void {
    this.loading = false;
    this.errorMessage = err?.error?.error || err?.message || 'Error desconegut';
  }
}

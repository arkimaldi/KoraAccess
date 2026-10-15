/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';

import { TerminalsComponent } from './terminals/terminals.component';
import { LanguageService } from './services/language.service';

@Component({
  selector: 'kora-root',
  standalone: true,
  imports: [CommonModule, TranslateModule, TerminalsComponent],
  template: `
    <header class="topbar">
      <h1>KoraAccess</h1>
      <span class="subtitle">{{ 'Access control' | translate }}</span>
      <!-- [selected] a cada opció i no [value] al select: les opcions surten
           d'un *ngFor, i el [value] s'aplicaria abans que existissin. -->
      <select class="lang-select" aria-label="Language" (change)="onLanguage($event)">
        <option *ngFor="let l of language.supportedLanguages" [value]="l"
                [selected]="l === language.getLanguage()">{{ language.languageNames[l] }}</option>
      </select>
    </header>
    <main>
      <kora-terminals></kora-terminals>
    </main>
  `
})
export class AppComponent implements OnInit {

  constructor(public language: LanguageService) {}

  ngOnInit(): void {
    this.language.init();
  }

  onLanguage(event: Event): void {
    this.language.updateLanguage((event.target as HTMLSelectElement).value);
  }
}

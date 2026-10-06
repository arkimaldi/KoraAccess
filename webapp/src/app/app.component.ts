/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component } from '@angular/core';
import { TerminalsComponent } from './terminals/terminals.component';

@Component({
  selector: 'kora-root',
  standalone: true,
  imports: [TerminalsComponent],
  template: `
    <header class="topbar">
      <h1>KoraAccess</h1>
      <span class="subtitle">Control d'accessos</span>
    </header>
    <main>
      <kora-terminals></kora-terminals>
    </main>
  `
})
export class AppComponent {}

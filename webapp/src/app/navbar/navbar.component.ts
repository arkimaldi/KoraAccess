/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';

import { AuthService } from '../auth/auth.service';
import { LanguageService } from '../services/language.service';

/**
 * Barra de navegació. El menú de l'avatar fa servir el desplegable de Bootstrap
 * (data-bs-toggle), com el navbar de KapriCloudWebManager.
 */
@Component({
  selector: 'kora-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, TranslateModule],
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.css']
})
export class NavbarComponent {

  constructor(public auth: AuthService, public language: LanguageService) {}

  /** Inicials del nom complet, o del nom d'usuari si no en té. */
  readonly initials = computed(() => {
    const user = this.auth.user();
    if (!user) { return ''; }
    const words = (user.full_name || '').trim().split(/\s+/).filter(Boolean);
    const letters = words.length >= 2 ? words[0][0] + words[1][0]
                  : words.length === 1 ? words[0].slice(0, 2)
                  : user.username.slice(0, 2);
    return letters.toUpperCase();
  });

  setLanguage(language: string): void {
    this.language.updateLanguage(language);
    // Es desa també com a preferència de l'usuari.
    this.auth.setLanguage(language).subscribe({ error: () => undefined });
  }
}

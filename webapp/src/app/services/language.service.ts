/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Injectable } from '@angular/core';
import { registerLocaleData } from '@angular/common';
import localeCa from '@angular/common/locales/ca';
import localeEs from '@angular/common/locales/es';
import { TranslateService } from '@ngx-translate/core';

/** Clau on es desa l'idioma triat al navegador. */
const STORAGE_KEY = 'koraaccess.language';

/**
 * Idioma de la interfície. Adaptat del LanguageService de KapriCloudWebManager.
 *
 * Ordre de preferència en arrencar:
 *   1. l'idioma desat amb el selector;
 *   2. l'idioma del navegador;
 *   3. l'anglès.
 *
 * Quan hi hagi el mòdul d'usuaris, la preferència de l'usuari haurà d'entrar
 * aquí, per davant de les altres dues. És l'únic lloc que caldrà tocar.
 *
 * El servidor no rep l'idioma: tots els missatges els tradueix el frontend.
 */
@Injectable({ providedIn: 'root' })
export class LanguageService {

  /** La primera de la llista és la de reserva. */
  readonly supportedLanguages = ['en', 'ca', 'es'];

  /** Noms en el seu propi idioma: així cadascú reconeix el seu al selector. */
  readonly languageNames: Record<string, string> = {
    en: 'English',
    ca: 'Català',
    es: 'Español'
  };

  constructor(private translateService: TranslateService) {
    // Perquè les dates es mostrin en el format de cada idioma (l'anglès ve de sèrie).
    registerLocaleData(localeCa, 'ca');
    registerLocaleData(localeEs, 'es');
  }

  init(): void {
    this.translateService.setDefaultLang(this.supportedLanguages[0]);
    const saved = this.readSaved();
    this.apply(saved ?? navigator.language ?? this.supportedLanguages[0], false);
  }

  getLanguage(): string {
    return this.translateService.currentLang || this.translateService.getDefaultLang();
  }

  /** Canvi fet per l'usuari al selector: s'aplica i es desa. */
  updateLanguage(languageCode: string): void {
    this.apply(languageCode, true);
  }

  /** Redueix 'ca-ES' a 'ca' i cau a l'anglès si l'idioma no és suportat. */
  private normalize(languageCode: string): string {
    const short = (languageCode || '').slice(0, 2).toLowerCase();
    return this.supportedLanguages.includes(short) ? short : this.supportedLanguages[0];
  }

  private apply(languageCode: string, save: boolean): void {
    const language = this.normalize(languageCode);
    if (language !== this.translateService.currentLang) {
      this.translateService.use(language);
    }
    document.documentElement.lang = language;
    if (save) {
      try {
        localStorage.setItem(STORAGE_KEY, language);
      } catch {
        // Sense accés a localStorage: l'idioma es manté durant la sessió.
      }
    }
  }

  private readSaved(): string | null {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }
}

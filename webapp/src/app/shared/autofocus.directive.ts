/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { AfterViewInit, Directive, ElementRef } from '@angular/core';

/**
 * Posa el focus a l'element en aparèixer i en selecciona el text, de manera
 * que l'usuari pot començar a escriure o reemplaçar el valor de seguida.
 */
@Directive({
  selector: '[koraAutofocus]',
  standalone: true
})
export class AutofocusDirective implements AfterViewInit {

  constructor(private el: ElementRef<HTMLInputElement>) {}

  ngAfterViewInit(): void {
    // setTimeout perquè l'element ja estigui pintat abans d'enfocar-lo.
    setTimeout(() => {
      this.el.nativeElement.focus();
      this.el.nativeElement.select?.();
    });
  }
}

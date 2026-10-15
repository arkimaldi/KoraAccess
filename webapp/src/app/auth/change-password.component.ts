/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';

import { AuthService } from './auth.service';
import { MessageService } from '../services/message.service';
import { ApiMessage } from '../models/terminal.model';
import { AutofocusDirective } from '../shared/autofocus.directive';

/** Ha de coincidir amb PASSWORD_MIN_LENGTH del servidor, que és qui la fa complir. */
const PASSWORD_MIN_LENGTH = 10;

/**
 * Canvi de la pròpia contrasenya. Dos usos:
 *   - forced: després que algú l'hagi restablerta; no es pot cancel·lar.
 *   - voluntari: des del menú d'usuari.
 */
@Component({
  selector: 'kora-change-password',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule, AutofocusDirective],
  templateUrl: './change-password.component.html',
  styleUrls: ['./auth.css']
})
export class ChangePasswordComponent {

  @Input() forced = false;
  @Output() done = new EventEmitter<void>();

  readonly minLength = PASSWORD_MIN_LENGTH;
  readonly requiredMessage: ApiMessage = {
    message_key: 'MSG_PASSWORD_CHANGE_REQUIRED', params: {},
    message: 'You must change your password before continuing.'
  };

  current = '';
  next = '';
  confirm = '';
  busy = false;
  error: ApiMessage | null = null;

  constructor(public auth: AuthService, public messages: MessageService) {}

  submit(): void {
    if (this.busy) { return; }
    this.error = null;
    // Validació prèvia per a la comoditat de l'usuari. La de debò la fa el servidor.
    if (this.next !== this.confirm) {
      this.error = { message_key: '_sys_passwordsDoNotMatch', params: {}, message: 'The passwords do not match.' };
      return;
    }
    if (this.next.length < PASSWORD_MIN_LENGTH) {
      this.error = { message_key: 'MSG_PASSWORD_TOO_SHORT', params: { min: PASSWORD_MIN_LENGTH },
                     message: `The password must have at least ${PASSWORD_MIN_LENGTH} characters.` };
      return;
    }
    this.busy = true;
    this.auth.changePassword(this.current, this.next).subscribe({
      next: () => {
        this.busy = false;
        this.current = this.next = this.confirm = '';
        this.done.emit();
      },
      error: (err) => {
        this.busy = false;
        this.error = this.messages.fromHttpError(err);
      }
    });
  }
}

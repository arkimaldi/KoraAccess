/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';

import { AuthService } from './auth.service';
import { MessageService } from '../services/message.service';
import { ApiMessage } from '../models/terminal.model';
import { AutofocusDirective } from '../shared/autofocus.directive';

@Component({
  selector: 'kora-login',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule, AutofocusDirective],
  templateUrl: './login.component.html',
  styleUrls: ['./auth.css']
})
export class LoginComponent {

  username = '';
  password = '';
  busy = false;
  error: ApiMessage | null = null;

  /** Missatge de sessió caducada, el mateix que envia el servidor. */
  readonly expiredMessage: ApiMessage = {
    message_key: 'MSG_AUTH_REQUIRED', params: {}, message: 'Your session has expired. Please log in again.'
  };

  constructor(public auth: AuthService, public messages: MessageService) {}

  submit(): void {
    if (this.busy || !this.username || !this.password) { return; }
    this.busy = true;
    this.error = null;
    this.auth.login(this.username, this.password).subscribe({
      next: () => { this.busy = false; },
      error: (err) => {
        this.busy = false;
        this.password = '';
        this.error = this.messages.fromHttpError(err);
      }
    });
  }
}

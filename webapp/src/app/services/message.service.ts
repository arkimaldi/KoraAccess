/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

import { Injectable } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { TranslateService } from '@ngx-translate/core';

import { ApiMessage } from '../models/terminal.model';

/**
 * Tradueix els missatges que envia el servidor.
 *
 * El servidor envia una clau estable (message_key), uns paràmetres i un text
 * anglès de reserva (message). Aquí es tradueix la clau; si no té traducció,
 * es mostra el text de reserva, que és millor que ensenyar la clau.
 */
@Injectable({ providedIn: 'root' })
export class MessageService {

  constructor(private translate: TranslateService) {}

  text(msg: ApiMessage | null | undefined): string {
    if (!msg) { return ''; }
    const translated = this.translate.instant(msg.message_key, msg.params || {});
    return translated && translated !== msg.message_key ? translated : (msg.message || msg.message_key);
  }

  /**
   * Converteix un error HTTP en un missatge. Els errors del servidor ja porten
   * la forma comuna; els de xarxa (sense resposta) no porten cos.
   */
  fromHttpError(err: unknown): ApiMessage {
    const httpError = err as HttpErrorResponse;
    const body = httpError?.error;
    if (body && typeof body === 'object' && 'message_key' in body) {
      return body as ApiMessage;
    }
    if (httpError?.status === 0) {
      return { message_key: '_sys_networkError', params: {}, message: 'Cannot reach the server.' };
    }
    return { message_key: '_sys_unexpectedError', params: {}, message: 'Unexpected error.' };
  }
}

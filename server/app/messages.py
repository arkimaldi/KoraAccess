# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Missatges que el servidor envia a la webapp.

El servidor NO tradueix: no sap ni necessita saber l'idioma de l'usuari. Envia
una clau estable i uns paràmetres, i és el frontend qui la tradueix amb
ngx-translate. Tots els missatges tenen la mateixa forma:

    {"message_key": "MSG_LICENSE_LIMIT_REACHED",
     "params": {"assigned": 20, "limit": 20},
     "message": "License limit reached (20/20)."}

`message` és el text anglès ja interpolat. Serveix per als logs, per a
qualsevol client de l'API i com a reserva si al frontend li falta la clau.

Les traduccions són a webapp/src/assets/i18n/{en,ca,es}.json, amb els
paràmetres en la sintaxi d'ngx-translate ({{assigned}}). Aquí el text anglès fa
servir la sintaxi de Python ({assigned}). La prova server/tests/test_i18n.py
comprova que cada clau existeix en tots els idiomes i que els paràmetres
coincideixen.

Claus estables, no el text anglès com a clau: així es pot corregir la redacció
sense trencar les traduccions.
"""

from flask import jsonify


class Msg:
    # -- genèrics
    INTERNAL_ERROR = 'MSG_INTERNAL_ERROR'
    DEVICE_UNKNOWN = 'MSG_DEVICE_UNKNOWN'

    # -- vinculació
    DEVICE_NOT_DISCOVERED = 'MSG_DEVICE_NOT_DISCOVERED'
    DEVICE_ALREADY_LINKED = 'MSG_DEVICE_ALREADY_LINKED'
    DEVICE_ALREADY_REGISTERED = 'MSG_DEVICE_ALREADY_REGISTERED'
    LINK_SEND_FAILED = 'MSG_LINK_SEND_FAILED'

    # -- alliberament i esborrat
    RELEASE_NOT_ENROLLED = 'MSG_RELEASE_NOT_ENROLLED'
    RELEASE_DEVICE_ASSIGNED = 'MSG_RELEASE_DEVICE_ASSIGNED'
    DELETE_REQUIRES_SEVERE_LOST = 'MSG_DELETE_REQUIRES_SEVERE_LOST'
    DELETE_ENROLLED_DEVICE = 'MSG_DELETE_ENROLLED_DEVICE'

    # -- descripció
    DESCRIPTION_NOT_EDITABLE = 'MSG_DESCRIPTION_NOT_EDITABLE'
    DESCRIPTION_TOO_LONG = 'MSG_DESCRIPTION_TOO_LONG'

    # -- assignació a porta
    ASSIGN_NOT_ENROLLED = 'MSG_ASSIGN_NOT_ENROLLED'
    DEVICE_ALREADY_ASSIGNED = 'MSG_DEVICE_ALREADY_ASSIGNED'
    DEVICE_NOT_ASSIGNED = 'MSG_DEVICE_NOT_ASSIGNED'
    LICENSE_LIMIT_REACHED = 'MSG_LICENSE_LIMIT_REACHED'

    # -- autenticació
    AUTH_REQUIRED = 'MSG_AUTH_REQUIRED'
    LOGIN_INVALID = 'MSG_LOGIN_INVALID'
    LOGIN_RATE_LIMITED = 'MSG_LOGIN_RATE_LIMITED'
    REQUEST_HEADER_MISSING = 'MSG_REQUEST_HEADER_MISSING'
    PASSWORD_CHANGE_REQUIRED = 'MSG_PASSWORD_CHANGE_REQUIRED'
    PASSWORD_CURRENT_INVALID = 'MSG_PASSWORD_CURRENT_INVALID'
    PASSWORD_TOO_SHORT = 'MSG_PASSWORD_TOO_SHORT'
    PASSWORD_TOO_LONG = 'MSG_PASSWORD_TOO_LONG'
    PASSWORD_SAME_AS_CURRENT = 'MSG_PASSWORD_SAME_AS_CURRENT'
    LANGUAGE_UNSUPPORTED = 'MSG_LANGUAGE_UNSUPPORTED'

    # -- gestió d'usuaris
    FORBIDDEN = 'MSG_FORBIDDEN'
    NOT_FOUND = 'MSG_NOT_FOUND'
    USER_UNKNOWN = 'MSG_USER_UNKNOWN'
    USERNAME_INVALID = 'MSG_USERNAME_INVALID'
    USERNAME_TAKEN = 'MSG_USERNAME_TAKEN'
    ROLE_INVALID = 'MSG_ROLE_INVALID'
    FULL_NAME_TOO_LONG = 'MSG_FULL_NAME_TOO_LONG'
    LAST_ADMIN = 'MSG_LAST_ADMIN'
    CANNOT_MODIFY_SELF = 'MSG_CANNOT_MODIFY_SELF'
    USERNAME_RESERVED = 'MSG_USERNAME_RESERVED'
    DELETE_ACTIVE_USER = 'MSG_DELETE_ACTIVE_USER'

    # -- avisos de la pantalla de Terminals
    WARN_RESET_EXTERNALLY = 'MSG_WARN_RESET_EXTERNALLY'
    WARN_POINTS_ELSEWHERE = 'MSG_WARN_POINTS_ELSEWHERE'
    WARN_CANNOT_REACH_SERVER = 'MSG_WARN_CANNOT_REACH_SERVER'
    WARN_UNKNOWN_POINTS_HERE = 'MSG_WARN_UNKNOWN_POINTS_HERE'


# Text anglès de reserva. Els paràmetres en sintaxi de Python.
MESSAGES = {
    Msg.INTERNAL_ERROR: 'Internal server error.',
    Msg.DEVICE_UNKNOWN: 'Unknown device.',

    Msg.DEVICE_NOT_DISCOVERED: 'The device does not appear in the discovery.',
    Msg.DEVICE_ALREADY_LINKED: 'The device is already linked to a server.',
    Msg.DEVICE_ALREADY_REGISTERED: 'The device {eui64} is already registered as {status}.',
    Msg.LINK_SEND_FAILED: 'The record was created, but the link request could not be sent to the device.',

    Msg.RELEASE_NOT_ENROLLED: 'Only an enrolled device can be released.',
    Msg.RELEASE_DEVICE_ASSIGNED: 'The terminal must first be replaced on its door.',
    Msg.DELETE_REQUIRES_SEVERE_LOST: 'A record can only be deleted manually when the device is severely lost.',
    Msg.DELETE_ENROLLED_DEVICE: 'An enrolled device must be released, not deleted.',

    Msg.DESCRIPTION_NOT_EDITABLE: 'The description can only be edited on enrolled or pending devices.',
    Msg.DESCRIPTION_TOO_LONG: 'The description cannot exceed {max} characters.',

    Msg.ASSIGN_NOT_ENROLLED: 'Only an enrolled device can be assigned.',
    Msg.DEVICE_ALREADY_ASSIGNED: 'The device is already assigned to a door.',
    Msg.DEVICE_NOT_ASSIGNED: 'The device is not assigned.',
    Msg.LICENSE_LIMIT_REACHED: 'License limit reached ({assigned}/{limit}).',

    Msg.AUTH_REQUIRED: 'Your session has expired. Please log in again.',
    Msg.LOGIN_INVALID: 'Incorrect username or password.',
    Msg.LOGIN_RATE_LIMITED: 'Too many login attempts. Please wait a minute and try again.',
    Msg.REQUEST_HEADER_MISSING: 'The request was rejected because a required header is missing.',
    Msg.PASSWORD_CHANGE_REQUIRED: 'You must change your password before continuing.',
    Msg.PASSWORD_CURRENT_INVALID: 'The current password is incorrect.',
    Msg.PASSWORD_TOO_SHORT: 'The password must have at least {min} characters.',
    Msg.PASSWORD_TOO_LONG: 'The password cannot exceed {max} characters.',
    Msg.PASSWORD_SAME_AS_CURRENT: 'The new password must be different from the current one.',
    Msg.LANGUAGE_UNSUPPORTED: 'Unsupported language.',

    Msg.FORBIDDEN: 'You do not have permission to perform this action.',
    Msg.NOT_FOUND: 'Not found.',
    Msg.USER_UNKNOWN: 'Unknown user.',
    Msg.USERNAME_INVALID: ('The username must have between {min} and {max} characters, using only '
                           'lowercase letters, digits, dots, hyphens and underscores.'),
    Msg.USERNAME_TAKEN: 'The username {username} is already in use.',
    Msg.ROLE_INVALID: 'Unknown role.',
    Msg.FULL_NAME_TOO_LONG: 'The full name cannot exceed {max} characters.',
    Msg.LAST_ADMIN: 'There must always be at least one active administrator.',
    Msg.CANNOT_MODIFY_SELF: 'You cannot deactivate yourself or remove your own administrator role.',
    Msg.USERNAME_RESERVED: 'Usernames starting with {prefix} are reserved.',
    Msg.DELETE_ACTIVE_USER: 'Deactivate the user before deleting it.',

    Msg.WARN_RESET_EXTERNALLY: 'The device has been reset externally: its record must be deleted.',
    Msg.WARN_POINTS_ELSEWHERE: 'The device now points to another server: a physical reset is required.',
    Msg.WARN_CANNOT_REACH_SERVER: ('The device points to this server but cannot reach it: '
                                   'check that it resolves the domain through the local DNS.'),
    Msg.WARN_UNKNOWN_POINTS_HERE: ('The device points to this server but is not registered: '
                                   'a physical reset is required to recover it.'),
}


def message(key, **params):
    """Construeix un missatge amb la forma comuna."""
    text = MESSAGES[key]
    try:
        text = text.format(**params)
    except (KeyError, IndexError):
        pass   # un paràmetre que falta no ha d'impedir respondre
    return {'message_key': key, 'params': params, 'message': text}


class AppError(Exception):
    """
    Error de negoci amb el seu codi HTTP.

    El codi és gruixut (400, 404, 409, 500): la precisió la dona la clau. Si dos
    casos necessiten un comportament diferent a la pantalla, s'han de distingir
    per la clau, no pel codi.
    """

    def __init__(self, key, http_status=400, **params):
        super().__init__(MESSAGES.get(key, key))
        self.key = key
        self.http_status = http_status
        self.params = params

    def response(self):
        return jsonify(message(self.key, **self.params)), self.http_status

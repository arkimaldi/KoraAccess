# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""Constants compartides."""


class DeviceStatus:
    """Cicle de vida d'un dispositiu (Devices.status)."""
    ENROLL_PENDING = 'enroll_pending'
    ENROLLED = 'enrolled'
    DELETE_PENDING = 'delete_pending'


class LinkState:
    """Estat de connexió (Devices.link). Independent del cicle de vida."""
    ONLINE = 'online'
    LOST = 'lost'
    SEVERE_LOST = 'severe_lost'
    OFFLINE = 'offline'


class MsgType:
    """Tipus de missatge del protocol CloudKimaldi."""
    ON_CLOUD_KEEP_ALIVE = 'on_cloud_keep_alive'
    ANS_CLOUD_BATCH = 'ans_cloud_batch'
    INS_CLOUD_BATCH = 'ins_cloud_batch'
    INS_CPU_GET_DEVICE_INFO = 'ins_cpu_get_device_info'
    INS_WEB_CREDENTIALS_SET = 'ins_web_credentials_set'
    INS_CFG_WRITE = 'ins_cfg_write'
    INS_CFG_APPLY = 'ins_cfg_apply'


class MsgId:
    """Etiquetes de lot (msgId.name) i d'instrucció."""
    ENROLL_DEVICE_STEP_2 = 'enroll_device_step_2'
    DELETE_DEVICE_STEP_2 = 'delete_device_step_2'
    GET_INFO = 'get_info'
    SECURIZE = 'securize'
    DESECURIZE = 'desecurize'
    SET_TOKEN = 'set_token'
    CLEAR_TOKEN = 'clear_token'
    APPLY = 'apply'


# Credencials de fàbrica del web d'administració del dispositiu
WEB_DEFAULT_USER = 'admin'
WEB_DEFAULT_PASSWORD = 'admin'

UC_RET_OK = 0

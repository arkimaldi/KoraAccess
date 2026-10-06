/** (C) 2026 Kimaldi Electronics,s.l. Tots els drets reservats. */

/**
 * Etiqueta de presentació, calculada pel servidor a partir del registre a
 * Devices, la presència a PortalDevices i la darrera observació de discovery.
 * No és una màquina d'estats.
 */
export type TerminalLabel =
  | 'FREE'
  | 'LINKED'
  | 'ENROLLED'
  | 'ASSIGNED'
  | 'FOREIGN'
  | 'DELETE_PENDING';

/** Estat de connexió, independent del cicle de vida. */
export type LinkState = 'online' | 'lost' | 'severe_lost' | 'offline' | null;

export interface Terminal {
  device_id: string | null;
  eui64: string;
  description: string;
  status: string | null;
  label: TerminalLabel;
  link: LinkState;
  link_kick_dts: string | null;
  knet_id: number | null;
  image_version: string | null;
  ip_address: string | null;
  web_securized: boolean | null;
  portal_name: string | null;
  is_assigned: boolean;
  seen_in_discovery: boolean;
  warnings: string[];
  can_assign: boolean;
  can_release: boolean;
  can_delete: boolean;
  can_link?: boolean;
}

export interface LicenseInfo {
  assigned: number;
  limit: number;
}

export interface TerminalsResponse {
  terminals: Terminal[];
  license: LicenseInfo;
  server_url: string;
}

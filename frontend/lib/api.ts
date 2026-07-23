const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type WriteKeyCreated = {
  id: string;
  key: string;
  created_at: string;
};

export type WriteKeyMasked = {
  id: string;
  masked_key: string;
  created_at: string;
  revoked_at: string | null;
};

export async function listWriteKeys(): Promise<WriteKeyMasked[]> {
  const res = await fetch(`${API_BASE_URL}/write-keys`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to list write keys: ${res.status}`);
  return res.json();
}

export async function createWriteKey(): Promise<WriteKeyCreated> {
  const res = await fetch(`${API_BASE_URL}/write-keys`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to create write key: ${res.status}`);
  return res.json();
}

export async function revokeWriteKey(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/write-keys/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to revoke write key: ${res.status}`);
}

export type HubSpotConnectionStatus = {
  connected: boolean;
  connected_at: string | null;
};

export type HubSpotSyncStatus = {
  hubspot_portal_id: string | null;
  scopes: string[] | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
};

export const HUBSPOT_AUTHORIZE_URL = `${API_BASE_URL}/oauth/hubspot/authorize`;

export async function getHubSpotStatus(): Promise<HubSpotConnectionStatus> {
  const res = await fetch(`${API_BASE_URL}/oauth/hubspot/status`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to get HubSpot status: ${res.status}`);
  return res.json();
}

export async function getHubSpotSyncStatus(): Promise<HubSpotSyncStatus | null> {
  const res = await fetch(`${API_BASE_URL}/oauth/hubspot/sync-status`, {
    cache: "no-store",
    credentials: "include",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to get HubSpot sync status: ${res.status}`);
  return res.json();
}

export async function disconnectHubSpot(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/oauth/hubspot`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to disconnect HubSpot: ${res.status}`);
}

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

export type HubspotStatusResponse = {
  connected: boolean;
  hubspot_portal_id: string | null;
  scopes: string[] | null;
  connected_at: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
};

export type HubspotConnectResponse = {
  authorize_url: string;
};

export async function getHubSpotStatus(): Promise<HubspotStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/integrations/hubspot/status`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to fetch HubSpot status: ${res.status}`);
  return res.json();
}

export async function getHubSpotConnectUrl(): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/integrations/hubspot/connect`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to get HubSpot connect URL: ${res.status}`);
  const data = await res.json();
  return data.authorize_url;
}

export async function disconnectHubSpot(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/integrations/hubspot`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Failed to disconnect HubSpot: ${res.status}`);
}


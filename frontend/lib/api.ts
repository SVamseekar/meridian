const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Matches scripts/seed_dev_tenant.py's DEV_TENANT_ID — fixed until real
// tenant auth exists (see docs/guidelines/build-sequence.md step 2 note).
export const DEV_TENANT_ID = "00000000-0000-0000-0000-000000000001";

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
  const res = await fetch(`${API_BASE_URL}/tenants/${DEV_TENANT_ID}/write-keys`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to list write keys: ${res.status}`);
  return res.json();
}

export async function createWriteKey(): Promise<WriteKeyCreated> {
  const res = await fetch(`${API_BASE_URL}/tenants/${DEV_TENANT_ID}/write-keys`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to create write key: ${res.status}`);
  return res.json();
}

export async function revokeWriteKey(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/tenants/${DEV_TENANT_ID}/write-keys/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to revoke write key: ${res.status}`);
}

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

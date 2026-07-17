"use client";

import { useEffect, useState } from "react";
import { listWriteKeys, revokeWriteKey, WriteKeyMasked } from "@/lib/api";

export default function WriteKeyList({ refreshToken }: { refreshToken: number }) {
  const [keys, setKeys] = useState<WriteKeyMasked[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listWriteKeys()
      .then(setKeys)
      .finally(() => setLoading(false));
  }, [refreshToken]);

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this write key? This cannot be undone.")) return;
    await revokeWriteKey(id);
    const updated = await listWriteKeys();
    setKeys(updated);
  }

  if (loading) return <p>Loading write keys…</p>;
  if (keys.length === 0) return <p>No write keys yet.</p>;

  return (
    <table data-testid="write-key-list">
      <thead>
        <tr>
          <th>Key</th>
          <th>Created</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => (
          <tr key={k.id} data-testid="write-key-row">
            <td>{k.masked_key}</td>
            <td>{new Date(k.created_at).toLocaleDateString()}</td>
            <td>{k.revoked_at ? "Revoked" : "Active"}</td>
            <td>
              {!k.revoked_at && (
                <button onClick={() => handleRevoke(k.id)}>Revoke</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

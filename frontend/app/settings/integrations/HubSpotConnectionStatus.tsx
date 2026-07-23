"use client";

import { useEffect, useState } from "react";
import {
  disconnectHubSpot,
  getHubSpotStatus,
  getHubSpotSyncStatus,
  HUBSPOT_AUTHORIZE_URL,
  HubSpotConnectionStatus as StatusType,
  HubSpotSyncStatus as SyncStatusType,
} from "@/lib/api";

export default function HubSpotConnectionStatus() {
  const [status, setStatus] = useState<StatusType | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatusType | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  useEffect(() => {
    getHubSpotStatus().then((s) => {
      setStatus(s);
      if (s.connected) {
        getHubSpotSyncStatus().then(setSyncStatus);
      }
    });
  }, []);

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      await disconnectHubSpot();
      setStatus({ connected: false, connected_at: null });
      setSyncStatus(null);
    } finally {
      setDisconnecting(false);
    }
  }

  if (status === null) return <p>Loading…</p>;

  return (
    <div>
      <p data-testid="hubspot-status">{status.connected ? "Connected" : "Not connected"}</p>
      {!status.connected && (
        <a href={HUBSPOT_AUTHORIZE_URL} data-testid="hubspot-connect-button">
          <button>Connect HubSpot</button>
        </a>
      )}
      {status.connected && (
        <>
          {syncStatus?.last_sync_status && (
            <p data-testid="hubspot-sync-status">
              Last sync:{" "}
              {syncStatus.last_sync_status === "failed"
                ? `Failed${syncStatus.last_sync_error ? ` — ${syncStatus.last_sync_error}` : ""}`
                : "Succeeded"}
              {syncStatus.last_sync_at ? ` at ${new Date(syncStatus.last_sync_at).toLocaleString()}` : ""}
            </p>
          )}
          <button data-testid="hubspot-disconnect-button" onClick={handleDisconnect} disabled={disconnecting}>
            {disconnecting ? "Disconnecting…" : "Disconnect HubSpot"}
          </button>
        </>
      )}
    </div>
  );
}

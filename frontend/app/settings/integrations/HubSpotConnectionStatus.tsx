"use client";

import { useEffect, useState } from "react";
import { getHubSpotStatus, HUBSPOT_AUTHORIZE_URL, HubSpotConnectionStatus as StatusType } from "@/lib/api";

export default function HubSpotConnectionStatus() {
  const [status, setStatus] = useState<StatusType | null>(null);

  useEffect(() => {
    getHubSpotStatus().then(setStatus);
  }, []);

  if (status === null) return <p>Loading…</p>;

  return (
    <div>
      <p data-testid="hubspot-status">{status.connected ? "Connected" : "Not connected"}</p>
      {!status.connected && (
        <a href={HUBSPOT_AUTHORIZE_URL} data-testid="hubspot-connect-button">
          <button>Connect HubSpot</button>
        </a>
      )}
    </div>
  );
}

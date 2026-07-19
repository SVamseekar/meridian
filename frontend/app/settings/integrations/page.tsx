"use client";

import { useEffect, useState } from "react";
import HubSpotConnectionStatus from "./HubSpotConnectionStatus";

export default function IntegrationsPage() {
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") === "1") {
      setBanner("HubSpot connected successfully.");
    } else if (params.get("error")) {
      setBanner(`Connection failed: ${params.get("error")}`);
    }
    if (params.has("connected") || params.has("error")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  return (
    <div>
      <h1>Integrations</h1>
      {banner && (
        <p data-testid="hubspot-callback-banner" role="alert">
          {banner}
        </p>
      )}
      <h2>HubSpot</h2>
      <HubSpotConnectionStatus />
    </div>
  );
}

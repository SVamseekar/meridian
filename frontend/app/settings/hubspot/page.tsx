"use client";

import { useEffect, useState } from "react";
import {
  disconnectHubSpot,
  getHubSpotConnectUrl,
  getHubSpotStatus,
  HubspotStatusResponse,
} from "@/lib/api";

export default function HubSpotSettingsPage() {
  const [status, setStatus] = useState<HubspotStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    // Check URL parameters for OAuth status redirects
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") === "1") {
      setSuccessMsg("HubSpot account connected successfully!");
    } else if (params.get("error")) {
      setErrorMsg(`Failed to connect HubSpot: ${params.get("error")}`);
    }
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      setLoading(true);
      const data = await getHubSpotStatus();
      setStatus(data);
    } catch (err: any) {
      setErrorMsg("Failed to load HubSpot connection status.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect() {
    try {
      setActionLoading(true);
      setErrorMsg(null);
      const url = await getHubSpotConnectUrl();
      window.location.href = url;
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to initiate HubSpot OAuth connection");
      setActionLoading(false);
    }
  }

  async function handleDisconnect() {
    try {
      setActionLoading(true);
      setErrorMsg(null);
      setSuccessMsg(null);
      await disconnectHubSpot();
      await loadStatus();
      setSuccessMsg("HubSpot account disconnected.");
    } catch (err: any) {
      setErrorMsg("Failed to disconnect HubSpot.");
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: "600px" }}>
      <h1>HubSpot Integration</h1>
      <p>Connect your HubSpot CRM account to ingest company and deal data.</p>

      {errorMsg && (
        <div
          data-testid="error-message"
          style={{
            padding: "0.75rem",
            marginBottom: "1rem",
            backgroundColor: "#fee2e2",
            color: "#b91c1c",
            borderRadius: "4px",
          }}
        >
          {errorMsg}
        </div>
      )}

      {successMsg && (
        <div
          data-testid="success-message"
          style={{
            padding: "0.75rem",
            marginBottom: "1rem",
            backgroundColor: "#dcfce7",
            color: "#15803d",
            borderRadius: "4px",
          }}
        >
          {successMsg}
        </div>
      )}

      {loading ? (
        <p data-testid="loading-indicator">Loading status...</p>
      ) : status?.connected ? (
        <div
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
            padding: "1.5rem",
            backgroundColor: "#f9fafb",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span
              style={{
                display: "inline-block",
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                backgroundColor: "#22c55e",
              }}
            />
            <strong data-testid="connection-status">Status: Connected</strong>
          </div>

          {status.hubspot_portal_id && (
            <p style={{ marginTop: "1rem" }}>
              <strong>Portal ID:</strong>{" "}
              <span data-testid="portal-id">{status.hubspot_portal_id}</span>
            </p>
          )}

          {status.scopes && status.scopes.length > 0 && (
            <p>
              <strong>Granted Scopes:</strong>{" "}
              <span data-testid="scopes">{status.scopes.join(", ")}</span>
            </p>
          )}

          {status.last_sync_status && (
            <p>
              <strong>Last Sync:</strong>{" "}
              <span data-testid="last-sync-status">
                {status.last_sync_status === "failed"
                  ? `Failed${status.last_sync_at ? ` at ${new Date(status.last_sync_at).toLocaleString()}` : ""}${
                      status.last_sync_error ? ` — ${status.last_sync_error}` : ""
                    }`
                  : `Succeeded${status.last_sync_at ? ` at ${new Date(status.last_sync_at).toLocaleString()}` : ""}`}
              </span>
            </p>
          )}

          <button
            data-testid="disconnect-button"
            onClick={handleDisconnect}
            disabled={actionLoading}
            style={{
              marginTop: "1.5rem",
              padding: "0.5rem 1rem",
              backgroundColor: "#ef4444",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              cursor: actionLoading ? "not-allowed" : "pointer",
            }}
          >
            {actionLoading ? "Disconnecting..." : "Disconnect HubSpot"}
          </button>
        </div>
      ) : (
        <div
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
            padding: "1.5rem",
            backgroundColor: "#ffffff",
          }}
        >
          <p data-testid="connection-status">Status: Not connected</p>
          <button
            data-testid="connect-button"
            onClick={handleConnect}
            disabled={actionLoading}
            style={{
              marginTop: "1rem",
              padding: "0.6rem 1.2rem",
              backgroundColor: "#ff7a59", // HubSpot brand orange
              color: "#ffffff",
              fontWeight: "600",
              border: "none",
              borderRadius: "4px",
              cursor: actionLoading ? "not-allowed" : "pointer",
            }}
          >
            {actionLoading ? "Connecting..." : "Connect HubSpot"}
          </button>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import WriteKeyGenerateButton from "./WriteKeyGenerateButton";
import WriteKeyList from "./WriteKeyList";

const DEV_TENANT_NAME = "Meridian Dev Tenant";

export default function WriteKeysPage() {
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div>
      <p data-testid="tenant-label">Tenant: {DEV_TENANT_NAME}</p>
      <h1>Write Keys</h1>
      <WriteKeyGenerateButton onCreated={() => setRefreshToken((t) => t + 1)} />
      <WriteKeyList refreshToken={refreshToken} />
    </div>
  );
}

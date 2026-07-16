"use client";

import { useState } from "react";
import { createWriteKey } from "@/lib/api";

export default function WriteKeyGenerateButton({ onCreated }: { onCreated: () => void }) {
  const [revealedKey, setRevealedKey] = useState<string | null>(null);

  async function handleGenerate() {
    const created = await createWriteKey();
    setRevealedKey(created.key);
    onCreated();
  }

  function handleCopy() {
    if (revealedKey) navigator.clipboard.writeText(revealedKey);
  }

  function handleDismiss() {
    setRevealedKey(null);
  }

  if (revealedKey) {
    return (
      <div data-testid="write-key-reveal" role="alert">
        <p>
          <strong>Save this key now — you won&apos;t be able to see it again.</strong>
        </p>
        <code data-testid="revealed-key">{revealedKey}</code>
        <button onClick={handleCopy}>Copy</button>
        <button onClick={handleDismiss}>I&apos;ve saved it</button>
      </div>
    );
  }

  return <button onClick={handleGenerate}>Generate new key</button>;
}

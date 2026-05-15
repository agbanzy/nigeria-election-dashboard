"use client";

import Link from "next/link";

export default function MessagingPage() {
  return (
    <div className="max-w-2xl mx-auto p-6 space-y-4">
      <h1 className="text-xl font-extrabold text-primary">Messaging</h1>
      <p className="text-sm text-dim">
        Polling-agent SMS/WhatsApp flows are not part of the pan-Nigeria backbone.
        The legacy FCT-specific surface has been retired.
      </p>
      <p className="text-sm">
        <Link className="underline text-accent-green" href="/">
          ← Back to overview
        </Link>
      </p>
    </div>
  );
}

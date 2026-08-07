"use client";

import { V1ChatApp } from "./components/V1ChatApp";

// Root route -- the original, stable V1 experience. Behavior is unchanged from before
// this file was split; the actual UI now lives in components/V1ChatApp.tsx, shared with
// /v1 so the two routes are never two copies of the same logic.
export default function Home() {
  return <V1ChatApp apiPath="/api/chat" />;
}

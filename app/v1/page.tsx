"use client";

import { V1ChatApp } from "../components/V1ChatApp";

// Explicit V1 interview-demo route -- renders the exact same component as `/`,
// pointed at the explicit /api/v1/chat alias (which itself calls the same
// agents.orchestrator.handle_query() as /api/chat). No duplicated UI or
// orchestration logic; this route exists purely for a clearly labeled demo URL.
export default function V1Page() {
  return <V1ChatApp apiPath="/api/v1/chat" />;
}

import { useEffect } from "react";
import { useSWRConfig } from "swr";

const API = "http://localhost:8000";

export type Case = {
  id: number;
  created_at: string;
  updated_at: string;
  status: "new" | "triaged" | "scheduled" | "in_progress" | "resolved" | "cancelled";
  urgency: "low" | "normal" | "urgent";
  name: string;
  phone: string;
  issue_type: string;
  description: string;
  notes: string;
  calls?: Call[];
  events?: CaseEvent[];
};

export type CaseEvent = {
  id: number;
  case_id: number;
  ts: string;
  actor: string;
  field: string;
  old: string;
  new: string;
};

export type Message = {
  id: number;
  call_id: string;
  ts: string;
  role: "user" | "assistant";
  text: string;
};

export type Call = {
  id: string;
  case_id: number | null;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  messages: Message[];
  case?: Case | null;
};

export const fetcher = (path: string) => fetch(API + path).then((r) => r.json());

export const patchCase = (id: number, body: Partial<Case>) =>
  fetch(`${API}/cases/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());

export const addNote = (id: number, text: string) =>
  fetch(`${API}/cases/${id}/notes`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, author: "staff" }),
  }).then((r) => r.json());

export const getToken = () =>
  fetcher("/livekit/token") as Promise<{ url: string; token: string }>;

// Backend pings on every write; refetch all SWR keys. Polling stays as fallback.
export function useLive() {
  const { mutate } = useSWRConfig();
  useEffect(() => {
    let ws: WebSocket;
    let alive = true;
    const connect = () => {
      ws = new WebSocket("ws://localhost:8000/ws");
      ws.onmessage = () => mutate(() => true);
      ws.onclose = () => {
        if (alive) setTimeout(connect, 1000);
      };
    };
    connect();
    return () => {
      alive = false;
      ws.close();
    };
  }, [mutate]);
}

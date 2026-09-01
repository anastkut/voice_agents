const API = "http://localhost:8000";

export type Case = {
  id: number;
  created_at: string;
  updated_at: string;
  status: "new" | "in_progress" | "resolved";
  name: string;
  phone: string;
  issue_type: string;
  description: string;
  notes: string;
};

export const fetcher = (path: string) => fetch(API + path).then((r) => r.json());

export const patchCase = (id: number, body: Partial<Case>) =>
  fetch(`${API}/cases/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());

export const getToken = () =>
  fetcher("/livekit/token") as Promise<{ url: string; token: string }>;

"use client";

import Link from "next/link";
import useSWR from "swr";
import { Call, Case, fetcher, useLive } from "@/lib/api";
import Transcript from "./transcript";

const STATUS_STYLE: Record<Case["status"], string> = {
  new: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved: "bg-green-100 text-green-800",
};

export default function CaseList() {
  useLive();
  const { data: cases } = useSWR<Case[]>("/cases", fetcher, { refreshInterval: 2000 });
  const { data: calls } = useSWR<Call[]>("/calls", fetcher, { refreshInterval: 2000 });

  return (
    <>
      {calls && calls.length > 0 && <ActiveCalls calls={calls} />}
      <h1 className="mb-4 text-xl font-semibold">Cases</h1>
      {!cases ? (
        <p className="text-neutral-500">Loading…</p>
      ) : cases.length === 0 ? (
        <p className="text-neutral-500">No cases yet.</p>
      ) : (
        <CaseTable cases={cases} />
      )}
    </>
  );
}

function ActiveCalls({ calls }: { calls: Call[] }) {
  return (
    <div className="mb-6">
      <h2 className="mb-2 text-sm font-medium text-neutral-500">Active calls</h2>
      {calls.map((c) => (
        <details key={c.id} open className="mb-2 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm">
          <summary className="cursor-pointer">
            <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-green-500" />
            Call {c.id} · started {new Date(c.started_at).toLocaleTimeString()} ·{" "}
            {c.case ? (
              <Link href={`/cases/${c.case.id}`} className="text-blue-700 hover:underline">
                case {c.case.id} — {c.case.name}
              </Link>
            ) : (
              <span className="text-neutral-500">collecting details…</span>
            )}
          </summary>
          <Transcript messages={c.messages} />
        </details>
      ))}
    </div>
  );
}

function CaseTable({ cases }: { cases: Case[] }) {
  return (
    <table className="w-full border-collapse rounded bg-white text-sm shadow-sm">
      <thead>
        <tr className="border-b border-neutral-200 text-left text-neutral-500">
          <th className="px-3 py-2 font-medium">#</th>
          <th className="px-3 py-2 font-medium">Created</th>
          <th className="px-3 py-2 font-medium">Name</th>
          <th className="px-3 py-2 font-medium">Phone</th>
          <th className="px-3 py-2 font-medium">Issue</th>
          <th className="px-3 py-2 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {cases.map((c) => (
          <tr key={c.id} className="border-b border-neutral-100 hover:bg-neutral-50">
            <td className="px-3 py-2">
              <Link href={`/cases/${c.id}`} className="font-medium text-blue-700 hover:underline">
                {c.id}
              </Link>
            </td>
            <td className="px-3 py-2 text-neutral-500">{new Date(c.created_at).toLocaleString()}</td>
            <td className="px-3 py-2">
              <Link href={`/cases/${c.id}`} className="hover:underline">{c.name}</Link>
            </td>
            <td className="px-3 py-2">{c.phone}</td>
            <td className="px-3 py-2">{c.issue_type.replace("_", " ")}</td>
            <td className="px-3 py-2">
              <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[c.status]}`}>
                {c.status.replace("_", " ")}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

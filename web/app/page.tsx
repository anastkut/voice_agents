"use client";

import Link from "next/link";
import useSWR from "swr";
import { Case, fetcher } from "@/lib/api";

const STATUS_STYLE: Record<Case["status"], string> = {
  new: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved: "bg-green-100 text-green-800",
};

export default function CaseList() {
  const { data: cases } = useSWR<Case[]>("/cases", fetcher, { refreshInterval: 2000 });

  if (!cases) return <p className="text-neutral-500">Loading…</p>;
  if (cases.length === 0) return <p className="text-neutral-500">No cases yet.</p>;

  return (
    <>
      <h1 className="mb-4 text-xl font-semibold">Cases</h1>
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
    </>
  );
}

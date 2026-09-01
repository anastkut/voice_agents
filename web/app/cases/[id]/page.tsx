"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { Case, fetcher, patchCase, useLive } from "@/lib/api";
import Transcript from "../../transcript";

export default function CaseDetail() {
  useLive();
  const { id } = useParams<{ id: string }>();
  const { data, mutate } = useSWR<Case>(`/cases/${id}`, fetcher, { refreshInterval: 2000 });

  const [status, setStatus] = useState<Case["status"]>("new");
  const [notes, setNotes] = useState("");
  const [dirty, setDirty] = useState(false);

  // Re-seed the form from the server (e.g. a note added by voice) unless the user is mid-edit.
  useEffect(() => {
    if (data && !dirty) {
      setStatus(data.status);
      setNotes(data.notes);
    }
  }, [data, dirty]);

  if (!data) return <p className="text-neutral-500">Loading…</p>;

  const save = async () => {
    await patchCase(data.id, { status, notes });
    setDirty(false);
    mutate();
  };

  return (
    <>
      <Link href="/" className="text-sm text-blue-700 hover:underline">← All cases</Link>
      <h1 className="mt-2 mb-4 text-xl font-semibold">Case {data.id}</h1>

      <div className="mb-6 grid grid-cols-2 gap-x-8 gap-y-3 rounded bg-white p-4 text-sm shadow-sm">
        <Field label="Name" value={data.name} />
        <Field label="Phone" value={data.phone} />
        <Field label="Issue" value={data.issue_type.replace("_", " ")} />
        <Field label="Created" value={new Date(data.created_at).toLocaleString()} />
        <div className="col-span-2">
          <Field label="Description" value={data.description} />
        </div>
      </div>

      <div className="rounded bg-white p-4 text-sm shadow-sm">
        <label className="mb-1 block text-neutral-500">Status</label>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value as Case["status"]); setDirty(true); }}
          className="mb-4 rounded border border-neutral-300 px-2 py-1"
        >
          <option value="new">new</option>
          <option value="in_progress">in progress</option>
          <option value="resolved">resolved</option>
        </select>

        <label className="mb-1 block text-neutral-500">Notes</label>
        <textarea
          value={notes}
          onChange={(e) => { setNotes(e.target.value); setDirty(true); }}
          rows={5}
          className="mb-4 w-full rounded border border-neutral-300 px-2 py-1 font-mono text-xs"
        />

        <button
          onClick={save}
          disabled={!dirty}
          className="rounded bg-blue-700 px-4 py-1.5 font-medium text-white disabled:opacity-40"
        >
          Save
        </button>
        <span className="ml-3 text-neutral-400">
          updated {new Date(data.updated_at).toLocaleString()}
        </span>
      </div>

      {data.calls?.map((call) => (
        <div key={call.id} className="mt-6 rounded bg-white p-4 text-sm shadow-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium">Call {call.id}</span>
            {!call.ended_at && (
              <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                live
              </span>
            )}
            <span className="text-neutral-400">{new Date(call.started_at).toLocaleString()}</span>
          </div>
          <Transcript messages={call.messages} />
        </div>
      ))}
    </>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-neutral-500">{label}</div>
      <div>{value}</div>
    </div>
  );
}

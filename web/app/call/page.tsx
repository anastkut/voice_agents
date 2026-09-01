"use client";

import { useEffect, useState } from "react";
import { RoomEvent } from "livekit-client";
import { useRoomContext } from "@livekit/components-react";
import { getToken } from "@/lib/api";

export default function CallPage() {
  const room = useRoomContext();
  const [state, setState] = useState("idle");

  useEffect(() => {
    const update = () => setState(room.state === "disconnected" ? "idle" : room.state);
    update();
    room.on(RoomEvent.ConnectionStateChanged, update);
    return () => void room.off(RoomEvent.ConnectionStateChanged, update);
  }, [room]);

  const call = async () => {
    const { url, token } = await getToken();
    await room.connect(url, token);
    await room.localParticipant.setMicrophoneEnabled(true);
  };

  return (
    <>
      <h1 className="mb-2 text-xl font-semibold">Talk to city services</h1>
      <p className="mb-6 text-sm text-neutral-500">Status: {state}</p>
      {state === "connected" ? (
        <button
          onClick={() => room.disconnect()}
          className="rounded bg-red-600 px-4 py-1.5 font-medium text-white"
        >
          Hang up
        </button>
      ) : (
        <button
          onClick={call}
          disabled={state === "connecting"}
          className="rounded bg-blue-700 px-4 py-1.5 font-medium text-white disabled:opacity-40"
        >
          Call city services
        </button>
      )}
      <p className="mt-4 text-xs text-neutral-400">
        The call stays active while you browse the dashboard; hang up here to end it.
      </p>
    </>
  );
}

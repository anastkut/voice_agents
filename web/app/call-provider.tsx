"use client";

import { useState } from "react";
import { Room } from "livekit-client";
import { RoomAudioRenderer, RoomContext } from "@livekit/components-react";

// One Room for the whole app, mounted in the layout: the call and the agent's
// audio survive route changes and end only on an explicit hang up.
export default function CallProvider({ children }: { children: React.ReactNode }) {
  const [room] = useState(() => new Room());
  return (
    <RoomContext.Provider value={room}>
      <RoomAudioRenderer />
      {children}
    </RoomContext.Provider>
  );
}

"use client";

import { useEffect, useRef } from "react";
import { Message } from "@/lib/api";

export default function Transcript({ messages }: { messages: Message[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [messages.length]);

  if (messages.length === 0) return null;
  return (
    <div ref={ref} className="mt-2 max-h-64 space-y-1.5 overflow-y-auto">
      {messages.map((m) => (
        <div key={m.id} className={m.role === "user" ? "text-left" : "text-right"}>
          <span
            className={`inline-block max-w-[80%] rounded px-2 py-1 text-left text-xs ${
              m.role === "user"
                ? "border border-neutral-200 bg-white"
                : "bg-blue-700 text-white"
            }`}
          >
            {m.text}
          </span>
        </div>
      ))}
    </div>
  );
}

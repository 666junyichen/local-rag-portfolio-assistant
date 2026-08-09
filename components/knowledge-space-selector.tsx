"use client";

import { useEffect, useState } from "react";

export type KnowledgeSpace = {
  spaceId: string;
  name: string;
  description: string;
  status: "active" | "archived";
  documentCount: number;
};

const fallbackSpace: KnowledgeSpace = {
  spaceId: "portfolio",
  name: "Portfolio",
  description: "Public resume, internship, and project evidence.",
  status: "active",
  documentCount: 0,
};

export function usePublicKnowledgeSpaces() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([fallbackSpace]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/spaces", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Unable to load knowledge spaces.");
        if (!cancelled && payload.spaces?.length) setSpaces(payload.spaces);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Unable to load knowledge spaces.");
      });
    return () => { cancelled = true; };
  }, []);

  return { spaces, error };
}

export function KnowledgeSpaceSelector({
  spaces,
  value,
  onChange,
  multiple = false,
  label = "Knowledge space",
}: {
  spaces: KnowledgeSpace[];
  value: string[];
  onChange: (spaceIds: string[]) => void;
  multiple?: boolean;
  label?: string;
}) {
  const active = spaces.filter((space) => space.status === "active");
  const selected = value.length ? value : [active[0]?.spaceId || "portfolio"];

  if (!multiple) return <label className="spaceSelectLabel">
    <span>{label}</span>
    <select value={selected[0]} onChange={(event) => onChange([event.target.value])}>
      {active.map((space) => <option key={space.spaceId} value={space.spaceId}>{space.name} ({space.documentCount})</option>)}
    </select>
  </label>;

  return <fieldset className="spaceFieldset">
    <legend>{label} <small>{selected.length}/5</small></legend>
    <div className="spaceOptionGrid">
      {active.map((space) => {
        const checked = selected.includes(space.spaceId);
        const disabled = !checked && selected.length >= 5;
        return <label className={checked ? "spaceOption selected" : "spaceOption"} key={space.spaceId}>
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={() => {
              if (checked && selected.length > 1) onChange(selected.filter((id) => id !== space.spaceId));
              else if (!checked && selected.length < 5) onChange([...selected, space.spaceId]);
            }}
          />
          <span><strong>{space.name}</strong><small>{space.documentCount} documents</small></span>
        </label>;
      })}
    </div>
  </fieldset>;
}

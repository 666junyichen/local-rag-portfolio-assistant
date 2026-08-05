import cards from "../../data/portfolio_profile.json";

type ProfileCard = {
  fact_id: string;
  label: string;
  value: string;
  source_doc_ids: string[];
  updated_at?: string;
  visibility: "public" | "private";
};

export function publicProfileContext(): string {
  return (cards as ProfileCard[])
    .filter((card) => card.visibility === "public")
    .map((card) => `- ${card.label}: ${card.value} (source: ${card.source_doc_ids.join(", ")}; updated: ${card.updated_at || "unknown"})`)
    .join("\n");
}

import { ApiError, apiFetch } from "./client";

export { ApiError };

export type UpdateCategory = "f1_opt" | "o1a" | "general";
export type UpdateTimeRange = "month" | "year";

export interface ImmigrationUpdateResult {
  id: string;
  title: string;
  url: string;
  official_domain: string;
  snippet: string;
  relevance_score: number | null;
  published_date: string | null;
  category: UpdateCategory;
  source_type: "official_government";
  retrieved_at: string;
}

export interface UpdatesResponse {
  category: UpdateCategory;
  time_range: UpdateTimeRange;
  results: ImmigrationUpdateResult[];
  official_domains: string[];
  retrieved_at: string;
  cache_hit: boolean;
  disclaimer: string;
}

export async function getUpdates(category: UpdateCategory, time_range: UpdateTimeRange): Promise<UpdatesResponse> {
  const params = new URLSearchParams({ category, time_range });
  const response = await apiFetch(`/api/updates?${params.toString()}`);
  return response.json();
}

import { ApiError, apiFetch } from "./client";

export { ApiError };

export type ChatRole = "user" | "assistant";

export interface ChatHistoryMessage {
  role: ChatRole;
  content: string;
}

export type ChatAnswerMode = "document_grounded" | "insufficient_document_evidence";

export interface ChatCitation {
  source_key: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  excerpt: string;
}

export interface ChatProcessingMetadata {
  retrieved_source_count: number;
  repair_attempted: boolean;
}

export interface ChatResponse {
  answer: string;
  answer_mode: ChatAnswerMode;
  citations: ChatCitation[];
  searched_document_count: number;
  disclaimer: string;
  requires_professional_review: boolean;
  model: string | null;
  processing: ChatProcessingMetadata;
}

export async function askChat(question: string, history: ChatHistoryMessage[]): Promise<ChatResponse> {
  const response = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  return response.json();
}

/**
 * Shared pure helpers for the Ask Proofly chat page. Kept out of Chat.tsx
 * so they're independently testable without rendering React.
 */

import { ChatHistoryMessage, ChatRole } from "../api/chat";

const MAX_HISTORY_MESSAGES = 6;

/** A message as kept in the chat page's local (browser-only) state. */
export interface ChatUiMessage {
  role: ChatRole;
  content: string;
}

/**
 * Builds the `history` array to send with the next request: the last
 * `MAX_HISTORY_MESSAGES` prior turns, stripped down to just `role`/`content`
 * (matching the backend's `ChatHistoryMessage` cap exactly, so the request
 * never gets rejected for having too much history attached).
 */
export function toChatHistory(messages: ChatUiMessage[]): ChatHistoryMessage[] {
  return messages.slice(-MAX_HISTORY_MESSAGES).map((message) => ({ role: message.role, content: message.content }));
}

/** "page 3" suffix for a source card, or "" when no page number is known. */
export function formatSourceLocation(filename: string, pageNumber: number | null): string {
  return pageNumber ? `${filename}, page ${pageNumber}` : filename;
}

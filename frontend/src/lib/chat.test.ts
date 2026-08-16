import { describe, expect, it } from "vitest";
import { ChatUiMessage, formatSourceLocation, toChatHistory } from "./chat";

describe("toChatHistory", () => {
  it("maps messages to role/content pairs", () => {
    const messages: ChatUiMessage[] = [
      { role: "user", content: "When does my EAD expire?" },
      { role: "assistant", content: "June 30, 2027, per S1." },
    ];
    expect(toChatHistory(messages)).toEqual([
      { role: "user", content: "When does my EAD expire?" },
      { role: "assistant", content: "June 30, 2027, per S1." },
    ]);
  });

  it("keeps only the last 6 messages", () => {
    const messages: ChatUiMessage[] = Array.from({ length: 10 }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: `message ${i}`,
    }));

    const history = toChatHistory(messages);

    expect(history).toHaveLength(6);
    expect(history[0].content).toBe("message 4");
    expect(history[5].content).toBe("message 9");
  });

  it("returns an empty array for no prior messages", () => {
    expect(toChatHistory([])).toEqual([]);
  });
});

describe("formatSourceLocation", () => {
  it("appends the page number when known", () => {
    expect(formatSourceLocation("Maya_Patel_EAD_Summary.pdf", 2)).toBe("Maya_Patel_EAD_Summary.pdf, page 2");
  });

  it("omits the page suffix when unknown", () => {
    expect(formatSourceLocation("Maya_Patel_EAD_Summary.pdf", null)).toBe("Maya_Patel_EAD_Summary.pdf");
  });
});

import { request } from "@/lib/api";

export type ChatMessage = { role: "user" | "assistant"; content: string };

export const fetchMessages = async (): Promise<ChatMessage[]> => {
  const response = await request("/api/ai/messages");
  return response.json();
};

export const sendChatMessage = async (message: string): Promise<{ reply: string }> => {
  const response = await request("/api/ai/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return response.json();
};

import api from "./client";
import type {
  AgentConversation,
  AgentConversationDetail,
  AgentPendingAction,
  PaginatedResponse,
} from "../types";

export async function getAgentStatus() {
  const { data } = await api.get<{ ai_enabled: boolean }>("/agent/status/");
  return data;
}

export async function fetchAvailableModels(params: {
  ai_provider_type?: string;
  ai_api_url?: string;
  ai_api_key?: string;
}): Promise<string[]> {
  const { data } = await api.post<{ models: string[] }>("/agent/models/", params);
  return data.models;
}

export async function getConversations() {
  const { data } = await api.get<PaginatedResponse<AgentConversation>>(
    "/agent/conversations/"
  );
  return data.results;
}

export async function getConversation(id: string) {
  const { data } = await api.get<AgentConversationDetail>(
    `/agent/conversations/${id}/`
  );
  return data;
}

export async function createConversation(payload: {
  title?: string;
  context_item?: string;
}) {
  const { data } = await api.post<AgentConversation>(
    "/agent/conversations/",
    payload
  );
  return data;
}

export async function deleteConversation(id: string) {
  await api.delete(`/agent/conversations/${id}/`);
}

export async function acceptAction(id: string) {
  const { data } = await api.post<AgentPendingAction>(
    `/agent/pending-actions/${id}/accept/`
  );
  return data;
}

export async function rejectAction(id: string) {
  const { data } = await api.post<AgentPendingAction>(
    `/agent/pending-actions/${id}/reject/`
  );
  return data;
}

/**
 * Stream a chat message via SSE. Returns an AbortController so the caller can cancel.
 */
export function streamChat(
  conversationId: string,
  message: string,
  callbacks: {
    onToken: (content: string) => void;
    onPendingAction: (action: AgentPendingAction) => void;
    onError: (detail: string) => void;
    onDone: () => void;
  }
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(`/api/v1/agent/conversations/${conversationId}/chat/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        callbacks.onError(text);
        callbacks.onDone();
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onDone();
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6);
            try {
              const data = JSON.parse(jsonStr);
              if (eventType === "token") {
                callbacks.onToken(data.content);
              } else if (eventType === "pending_action") {
                callbacks.onPendingAction(data);
              } else if (eventType === "error") {
                callbacks.onError(data.detail || "Unknown error");
              } else if (eventType === "done") {
                callbacks.onDone();
              }
            } catch {
              // skip malformed JSON
            }
            eventType = "";
          }
        }
      }
      callbacks.onDone();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err.message);
        callbacks.onDone();
      }
    });

  return controller;
}

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  Send,
  Plus,
  Trash2,
  Loader2,
  Check,
  XCircle,
  ChevronDown,
  Bot,
  User,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "../auth/AuthContext";
import * as agentApi from "../api/agent";
import type { AgentPendingAction } from "../types";

interface Props {
  onClose: () => void;
  contextItemId?: string;
}

export default function AgentPanel({ onClose, contextItemId }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamedContent, setStreamedContent] = useState("");
  const [showConversationList, setShowConversationList] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const isEditor = user?.vault_role === "editor" || user?.vault_role === "admin";

  const { data: conversations } = useQuery({
    queryKey: ["agent-conversations"],
    queryFn: agentApi.getConversations,
  });

  const { data: conversation, refetch: refetchConversation } = useQuery({
    queryKey: ["agent-conversation", activeConversationId],
    queryFn: () => agentApi.getConversation(activeConversationId!),
    enabled: !!activeConversationId,
  });

  const createMutation = useMutation({
    mutationFn: agentApi.createConversation,
    onSuccess: (data) => {
      setActiveConversationId(data.id);
      queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: agentApi.deleteConversation,
    onSuccess: () => {
      setActiveConversationId(null);
      queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
    },
  });

  const acceptMutation = useMutation({
    mutationFn: agentApi.acceptAction,
    onSuccess: () => {
      refetchConversation();
      queryClient.invalidateQueries({ queryKey: ["items"] });
      queryClient.invalidateQueries({ queryKey: ["tree"] });
      queryClient.invalidateQueries({ queryKey: ["navigation"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: agentApi.rejectAction,
    onSuccess: () => refetchConversation(),
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages, streamedContent]);

  // Focus input
  useEffect(() => {
    if (!streaming) inputRef.current?.focus();
  }, [streaming, activeConversationId]);

  const handleNewConversation = useCallback(() => {
    createMutation.mutate({
      title: "",
      ...(contextItemId ? { context_item: contextItemId } : {}),
    });
    setShowConversationList(false);
  }, [contextItemId, createMutation]);

  const handleSend = useCallback(() => {
    if (!input.trim() || streaming) return;
    if (!activeConversationId) {
      // Create conversation first, then send
      const payload: { title?: string; context_item?: string } = {};
      if (contextItemId) payload.context_item = contextItemId;
      agentApi.createConversation(payload).then((conv) => {
        setActiveConversationId(conv.id);
        queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
        sendMessage(conv.id, input.trim());
      });
      return;
    }
    sendMessage(activeConversationId, input.trim());
  }, [input, streaming, activeConversationId, contextItemId, queryClient]);

  const sendMessage = (convId: string, message: string) => {
    setInput("");
    setStreaming(true);
    setStreamedContent("");

    abortRef.current = agentApi.streamChat(convId, message, {
      onToken: (content) => {
        setStreamedContent((prev) => prev + content);
      },
      onPendingAction: () => {
        refetchConversation();
      },
      onError: (detail) => {
        setStreamedContent((prev) => prev + `\n\n**Error:** ${detail}`);
      },
      onDone: () => {
        setStreaming(false);
        setStreamedContent("");
        refetchConversation();
      },
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Filter messages to hide system and tool messages from UI
  const visibleMessages = conversation?.messages?.filter(
    (m) => m.role === "user" || m.role === "assistant"
  ) || [];

  const pendingActions = conversation?.pending_actions || [];

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-96 flex-col border-l border-gray-200 bg-white shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-blue-600" />
          <span className="font-semibold text-gray-900">AI Assistant</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowConversationList((v) => !v)}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Conversations"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
          <button
            onClick={handleNewConversation}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="New conversation"
          >
            <Plus className="h-4 w-4" />
          </button>
          {activeConversationId && (
            <button
              onClick={() => deleteMutation.mutate(activeConversationId)}
              className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
              title="Delete conversation"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={onClose}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Conversation list dropdown */}
      {showConversationList && (
        <div className="border-b border-gray-200 bg-gray-50 px-2 py-2">
          <div className="max-h-48 overflow-y-auto space-y-1">
            {conversations?.map((conv) => (
              <button
                key={conv.id}
                onClick={() => {
                  setActiveConversationId(conv.id);
                  setShowConversationList(false);
                }}
                className={`flex w-full items-center rounded px-2 py-1.5 text-left text-sm ${
                  conv.id === activeConversationId
                    ? "bg-blue-100 text-blue-800"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <span className="truncate">
                  {conv.title || `Chat ${conv.created_at.slice(0, 10)}`}
                </span>
              </button>
            ))}
            {(!conversations || conversations.length === 0) && (
              <p className="px-2 py-1 text-xs text-gray-500">No conversations yet</p>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {visibleMessages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : ""}`}>
            {msg.role === "assistant" && (
              <Bot className="mt-1 h-5 w-5 shrink-0 text-blue-600" />
            )}
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
            {msg.role === "user" && (
              <User className="mt-1 h-5 w-5 shrink-0 text-gray-400" />
            )}
          </div>
        ))}

        {/* Streaming response */}
        {streaming && streamedContent && (
          <div className="flex gap-2">
            <Bot className="mt-1 h-5 w-5 shrink-0 text-blue-600" />
            <div className="max-w-[85%] rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-800">
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamedContent}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {streaming && !streamedContent && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking...
          </div>
        )}

        {/* Pending actions */}
        {pendingActions
          .filter((a) => a.status === "pending")
          .map((action) => (
            <PendingActionCard
              key={action.id}
              action={action}
              isEditor={isEditor}
              onAccept={() => acceptMutation.mutate(action.id)}
              onReject={() => rejectMutation.mutate(action.id)}
              accepting={acceptMutation.isPending}
              rejecting={rejectMutation.isPending}
            />
          ))}

        {/* Resolved actions */}
        {pendingActions
          .filter((a) => a.status !== "pending")
          .map((action) => (
            <ResolvedActionCard key={action.id} action={action} />
          ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-3">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask AI about your vault..."
            rows={1}
            className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={streaming}
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim()}
            className="rounded-lg bg-blue-600 p-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function PendingActionCard({
  action,
  isEditor,
  onAccept,
  onReject,
  accepting,
  rejecting,
}: {
  action: AgentPendingAction;
  isEditor: boolean;
  onAccept: () => void;
  onReject: () => void;
  accepting: boolean;
  rejecting: boolean;
}) {
  const labels: Record<string, string> = {
    create_item: "Create Item",
    update_item: "Update Item",
    create_relation: "Create Relation",
  };

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-800">
        <Bot className="h-4 w-4" />
        {labels[action.action_type] || action.action_type} — Pending Confirmation
      </div>
      <div className="mb-3 space-y-1 text-xs text-amber-700">
        {Object.entries(action.payload).map(([key, value]) => (
          <div key={key}>
            <span className="font-medium">{key}:</span>{" "}
            {typeof value === "object" ? JSON.stringify(value) : String(value)}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        {isEditor && (
          <button
            onClick={onAccept}
            disabled={accepting}
            className="flex items-center gap-1 rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {accepting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            Accept
          </button>
        )}
        <button
          onClick={onReject}
          disabled={rejecting}
          className="flex items-center gap-1 rounded bg-gray-200 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-300 disabled:opacity-50"
        >
          {rejecting ? <Loader2 className="h-3 w-3 animate-spin" /> : <XCircle className="h-3 w-3" />}
          Reject
        </button>
      </div>
    </div>
  );
}

function ResolvedActionCard({ action }: { action: AgentPendingAction }) {
  const labels: Record<string, string> = {
    create_item: "Create Item",
    update_item: "Update Item",
    create_relation: "Create Relation",
  };

  const statusColors: Record<string, string> = {
    executed: "border-green-200 bg-green-50 text-green-800",
    rejected: "border-gray-200 bg-gray-50 text-gray-600",
    failed: "border-red-200 bg-red-50 text-red-800",
  };

  const statusIcons: Record<string, React.ReactNode> = {
    executed: <Check className="h-3 w-3 text-green-600" />,
    rejected: <XCircle className="h-3 w-3 text-gray-500" />,
    failed: <XCircle className="h-3 w-3 text-red-500" />,
  };

  return (
    <div className={`rounded-lg border p-2 text-xs ${statusColors[action.status] || "border-gray-200 bg-gray-50"}`}>
      <div className="flex items-center gap-1">
        {statusIcons[action.status]}
        <span className="font-medium">
          {labels[action.action_type]} — {action.status}
        </span>
      </div>
    </div>
  );
}

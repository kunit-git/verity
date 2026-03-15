import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, Trash2, Inbox, X, ArrowLeft } from "lucide-react";
import { useConfirm } from "../components/ConfirmDialog";
import MermaidDiagram from "../components/MermaidDiagram";
import { getMailboxArtifacts, getMailboxArtifact, deleteMailboxArtifact } from "../api/mailbox";
import type { MailboxArtifactDetail } from "../types";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isMarkdown(filename: string): boolean {
  return /\.md$/i.test(filename);
}

export default function MailboxPage() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [viewing, setViewing] = useState<MailboxArtifactDetail | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const { data: artifacts, isLoading } = useQuery({
    queryKey: ["mailbox"],
    queryFn: getMailboxArtifacts,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMailboxArtifact,
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["mailbox"] });
      if (viewing?.id === deletedId) setViewing(null);
    },
  });

  async function handleView(id: string) {
    setLoadingId(id);
    try {
      const detail = await getMailboxArtifact(id);
      setViewing(detail);
    } finally {
      setLoadingId(null);
    }
  }

  async function handleDownload(id: string, filename: string) {
    const detail = viewing?.id === id ? viewing : await getMailboxArtifact(id);
    const blob = new Blob([detail.content], { type: detail.content_type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  // Markdown preview view
  if (viewing) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 border-b border-gray-200 bg-white px-4 py-3">
          <button
            onClick={() => setViewing(null)}
            className="rounded p-1 text-gray-500 hover:bg-gray-100"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <h1 className="flex-1 truncate text-lg font-semibold text-gray-900">
            {viewing.filename}
          </h1>
          <button
            onClick={() => handleDownload(viewing.id, viewing.filename)}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Download"
          >
            <Download className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewing(null)}
            className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto bg-white p-8">
          <article className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-li:text-gray-700 prose-hr:border-gray-200 prose-table:text-gray-700 prose-th:text-gray-900 prose-td:text-gray-700">
            <Markdown
              remarkPlugins={[remarkGfm]}
              components={{
                pre({ children }) {
                  // pre receives the unrendered <code> element as children,
                  // so check its className to detect mermaid blocks
                  const child = Array.isArray(children) ? children[0] : children;
                  const isMermaid = (child as React.ReactElement)?.props?.className?.includes("language-mermaid");
                  if (isMermaid) {
                    return <div className="my-4">{children}</div>;
                  }
                  return <pre>{children}</pre>;
                },
                code({ className, children }) {
                  const lang = /language-(\w+)/.exec(className || "")?.[1];
                  if (lang === "mermaid") {
                    return <MermaidDiagram source={String(children).trimEnd()} />;
                  }
                  return <code className={className}>{children}</code>;
                },
              }}
            >
              {viewing.content}
            </Markdown>
          </article>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center gap-3">
        <Inbox className="h-6 w-6 text-gray-700" />
        <h1 className="text-2xl font-bold text-gray-900">Mailbox</h1>
      </div>

      {!artifacts || artifacts.length === 0 ? (
        <p className="text-sm text-gray-500">
          No documents yet. Use the Generate Document button on any item to create one.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Filename
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Size
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Date
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {artifacts.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium">
                    {isMarkdown(a.filename) ? (
                      <button
                        onClick={() => handleView(a.id)}
                        disabled={loadingId === a.id}
                        className="text-blue-600 hover:text-blue-800 hover:underline disabled:opacity-50"
                      >
                        {loadingId === a.id ? "Loading..." : a.filename}
                      </button>
                    ) : (
                      <span className="text-gray-900">{a.filename}</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {formatFileSize(a.file_size)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                    {new Date(a.created_at).toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleDownload(a.id, a.filename)}
                        className="rounded p-1.5 text-gray-500 hover:bg-gray-100"
                        title="Download"
                      >
                        <Download className="h-4 w-4" />
                      </button>
                      <button
                        onClick={async () => {
                          if (await confirm("Delete this document?"))
                            deleteMutation.mutate(a.id);
                        }}
                        className="rounded p-1.5 text-red-500 hover:bg-red-50"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

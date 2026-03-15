import { useState, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getItemTypes, getDocumentTemplate, saveDocumentTemplate, deleteDocumentTemplate } from "../api/items";
import type { ItemType } from "../types";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmDialog";

export default function DocumentTemplateManager() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: itemTypes, isLoading } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  return (
    <div className="flex h-full">
      {/* Left panel — item type list */}
      <div className="w-72 shrink-0 border-r border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-4 py-3">
          <h1 className="text-lg font-bold text-gray-900">Doc Templates</h1>
          <p className="mt-0.5 text-xs text-gray-500">
            Customize Markdown templates per item type
          </p>
        </div>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          </div>
        ) : (
          <nav className="p-2 space-y-0.5">
            {itemTypes?.map((t) => (
              <ItemTypeRow
                key={t.id}
                itemType={t}
                selected={selectedId === t.id}
                onClick={() => setSelectedId(t.id)}
              />
            ))}
          </nav>
        )}
      </div>

      {/* Right panel — template editor */}
      <div className="flex-1 overflow-y-auto">
        {selectedId ? (
          <TemplateEditor itemTypeId={selectedId} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-gray-400">
            Select an item type to view or edit its template
          </div>
        )}
      </div>
    </div>
  );
}

function ItemTypeRow({
  itemType,
  selected,
  onClick,
}: {
  itemType: ItemType;
  selected: boolean;
  onClick: () => void;
}) {
  const { data } = useQuery({
    queryKey: ["docTemplate", itemType.id],
    queryFn: () => getDocumentTemplate(itemType.id),
  });

  const hasCustom = data?.template != null;

  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors ${
        selected ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-50"
      }`}
    >
      <span className="font-medium truncate">{itemType.name}</span>
      <span
        className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
          hasCustom
            ? "bg-blue-100 text-blue-700"
            : "bg-gray-100 text-gray-500"
        }`}
      >
        {hasCustom ? "Custom" : "Default"}
      </span>
    </button>
  );
}

function TemplateEditor({ itemTypeId }: { itemTypeId: string }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const confirm = useConfirm();
  const isEditor = user?.vault_role === "editor" || user?.vault_role === "admin";
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["docTemplate", itemTypeId],
    queryFn: () => getDocumentTemplate(itemTypeId),
  });

  const [mode, setMode] = useState<"custom" | "default">("custom");
  const [draft, setDraft] = useState<string | null>(null);

  // Reset draft when switching item types or data loads
  const currentTemplate = data?.template ?? "";
  const editValue = draft ?? currentTemplate;

  const saveMutation = useMutation({
    mutationFn: (template: string) => saveDocumentTemplate(itemTypeId, template),
    onSuccess: () => {
      setDraft(null);
      queryClient.invalidateQueries({ queryKey: ["docTemplate", itemTypeId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteDocumentTemplate(itemTypeId),
    onSuccess: () => {
      setDraft(null);
      queryClient.invalidateQueries({ queryKey: ["docTemplate", itemTypeId] });
    },
  });

  const insertField = useCallback(
    (field: string) => {
      const ta = textareaRef.current;
      if (!ta) return;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const value = editValue;
      const insert = `{{${field}}}`;
      const newValue = value.slice(0, start) + insert + value.slice(end);
      setDraft(newValue);
      // Restore cursor position after React re-render
      requestAnimationFrame(() => {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + insert.length;
      });
    },
    [editValue]
  );

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!data) return null;

  const hasCustom = data.template != null;

  return (
    <div className="p-6">
      {/* Mode toggle */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex rounded-md border border-gray-300 text-sm">
          <button
            onClick={() => setMode("custom")}
            className={`px-3 py-1.5 ${
              mode === "custom"
                ? "bg-blue-600 text-white"
                : "text-gray-600 hover:bg-gray-50"
            } rounded-l-md`}
          >
            Custom Template
          </button>
          <button
            onClick={() => setMode("default")}
            className={`px-3 py-1.5 ${
              mode === "default"
                ? "bg-blue-600 text-white"
                : "text-gray-600 hover:bg-gray-50"
            } rounded-r-md`}
          >
            Default Template
          </button>
        </div>

        {hasCustom && (
          <span className="text-xs text-gray-400">
            Last updated: {data.updated_at ? new Date(data.updated_at).toLocaleString() : "—"}
          </span>
        )}
      </div>

      {mode === "default" ? (
        <div>
          <p className="mb-2 text-xs text-gray-500">
            This is the built-in default template (read-only). Used when no custom template is set.
          </p>
          <pre className="rounded-lg border border-gray-200 bg-gray-100 p-4 text-sm text-gray-700 whitespace-pre-wrap font-mono">
            {data.default_template}
          </pre>
        </div>
      ) : (
        <div>
          {/* Available fields */}
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 mb-1.5">
              Available fields (click to insert):
            </p>
            <div className="flex flex-wrap gap-1.5">
              {data.available_fields.map((field) => (
                <button
                  key={field}
                  onClick={() => insertField(field)}
                  disabled={!isEditor}
                  className="rounded-full border border-gray-200 bg-white px-2.5 py-0.5 text-xs font-mono text-gray-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {`{{${field}}}`}
                </button>
              ))}
            </div>
          </div>

          {/* Editor */}
          <textarea
            ref={textareaRef}
            value={editValue}
            onChange={(e) => setDraft(e.target.value)}
            disabled={!isEditor}
            rows={18}
            className="w-full rounded-lg border border-gray-300 bg-white p-4 font-mono text-sm text-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:cursor-not-allowed"
            placeholder="Enter your custom Markdown template using {{field}} placeholders..."
          />

          {/* Actions */}
          {isEditor && (
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={() => saveMutation.mutate(editValue)}
                disabled={saveMutation.isPending}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saveMutation.isPending ? "Saving..." : "Save Template"}
              </button>
              {hasCustom && (
                <button
                  onClick={async () => {
                    if (await confirm("Delete custom template and revert to default?"))
                      deleteMutation.mutate();
                  }}
                  disabled={deleteMutation.isPending}
                  className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? "Deleting..." : "Delete Custom Template"}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

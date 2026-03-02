import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getItemTypes, createItem, getItem, updateItem } from "../api/items";
import { getRelationTypes, createRelation } from "../api/relations";
import type { CustomFieldDefinition } from "../types";

export default function ItemCreatePage({ editId }: { editId?: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const preselectedType = searchParams.get("type") || "";
  const parentId = searchParams.get("parent") || "";

  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  const { data: parentItem } = useQuery({
    queryKey: ["item", parentId],
    queryFn: () => getItem(parentId),
    enabled: !!parentId && !editId,
  });

  const { data: relationTypesList } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
    enabled: !!parentId && !editId,
  });

  const { data: editItem } = useQuery({
    queryKey: ["item", editId],
    queryFn: () => getItem(editId!),
    enabled: !!editId,
  });

  const [selectedTypeId, setSelectedTypeId] = useState(() => {
    if (editItem) return editItem.item_type;
    if (preselectedType && itemTypes) {
      const t = itemTypes.find((t) => t.slug === preselectedType);
      return t?.id || "";
    }
    return "";
  });
  const [title, setTitle] = useState(editItem?.title || "");
  const [description, setDescription] = useState(editItem?.description || "");
  const [status, setStatus] = useState(editItem?.status || "draft");
  const [customFields, setCustomFields] = useState<Record<string, unknown>>(
    editItem?.custom_fields || {}
  );
  const [error, setError] = useState("");

  const selectedType = itemTypes?.find((t) => t.id === selectedTypeId);

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        title,
        description,
        item_type: selectedTypeId,
        status,
        custom_fields: customFields,
      };
      if (editId) return updateItem(editId, payload);
      return createItem(payload);
    },
    onSuccess: async (data) => {
      // Auto-link to parent container if parent query param was provided
      if (parentId && !editId && relationTypesList) {
        const compType = relationTypesList.find(
          (rt) => rt.kind === "composition"
        );
        if (compType) {
          try {
            await createRelation({
              relation_type: compType.id,
              source: parentId,
              target: data.id,
            });
          } catch {
            // Item created but relation failed — navigate anyway
          }
        }
      }
      queryClient.invalidateQueries({ queryKey: ["items"] });
      queryClient.invalidateQueries({ queryKey: ["tree"] });
      queryClient.invalidateQueries({ queryKey: ["navigation"] });
      navigate(`/items/${data.id}`);
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed to save item");
    },
  });

  // When type changes, if we also need to update preselection
  function handleTypeChange(typeId: string) {
    setSelectedTypeId(typeId);
    setCustomFields({});
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-bold text-gray-900">
        {editId ? "Edit Item" : "Create New Item"}
      </h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
        className="mt-6 space-y-5"
      >
        {parentItem && !editId && (
          <div className="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-700">
            Will be added to <span className="font-medium">{parentItem.title}</span>
          </div>
        )}

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Item Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Item Type
          </label>
          <select
            value={selectedTypeId}
            onChange={(e) => handleTypeChange(e.target.value)}
            required
            disabled={!!editId}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
          >
            <option value="">Select a type...</option>
            {itemTypes?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Status */}
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Status
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="in_review">In Review</option>
            <option value="approved">Approved</option>
            <option value="archived">Archived</option>
          </select>
        </div>

        {/* Dynamic custom fields */}
        {selectedType && selectedType.custom_fields.length > 0 && (
          <div className="border-t border-gray-200 pt-5">
            <h3 className="text-sm font-semibold text-gray-700">
              {selectedType.name} Fields
            </h3>
            <div className="mt-3 space-y-4">
              {selectedType.custom_fields.map((fd) => (
                <DynamicField
                  key={fd.id}
                  field={fd}
                  value={customFields[fd.slug]}
                  onChange={(val) =>
                    setCustomFields((prev) => ({ ...prev, [fd.slug]: val }))
                  }
                />
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending
              ? "Saving..."
              : editId
                ? "Update Item"
                : "Create Item"}
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function DynamicField({
  field,
  value,
  onChange,
}: {
  field: CustomFieldDefinition;
  value: unknown;
  onChange: (val: unknown) => void;
}) {
  const label = (
    <label className="block text-sm font-medium text-gray-700">
      {field.name}
      {field.is_required && <span className="text-red-500"> *</span>}
    </label>
  );

  const inputClass =
    "mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

  switch (field.field_kind) {
    case "choice": {
      const choices = (field.options as { choices?: string[] })?.choices || [];
      return (
        <div>
          {label}
          <select
            value={(value as string) || ""}
            onChange={(e) => onChange(e.target.value || null)}
            required={field.is_required}
            className={inputClass}
          >
            <option value="">Select...</option>
            {choices.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      );
    }
    case "boolean":
      return (
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600"
          />
          <label className="text-sm font-medium text-gray-700">
            {field.name}
          </label>
        </div>
      );
    case "integer":
    case "decimal":
      return (
        <div>
          {label}
          <input
            type="number"
            step={field.field_kind === "decimal" ? "0.01" : "1"}
            value={(value as number) ?? ""}
            onChange={(e) =>
              onChange(e.target.value ? Number(e.target.value) : null)
            }
            required={field.is_required}
            className={inputClass}
          />
        </div>
      );
    case "date":
      return (
        <div>
          {label}
          <input
            type="date"
            value={(value as string) || ""}
            onChange={(e) => onChange(e.target.value || null)}
            required={field.is_required}
            className={inputClass}
          />
        </div>
      );
    default: // text
      return (
        <div>
          {label}
          <textarea
            value={(value as string) || ""}
            onChange={(e) => onChange(e.target.value || null)}
            required={field.is_required}
            rows={2}
            className={inputClass}
          />
        </div>
      );
  }
}

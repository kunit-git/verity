import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import {
  getItemTypes,
  createItemType,
  addCustomField,
  deleteCustomField,
  deleteItemType,
} from "../api/items";
import type { ItemType } from "../types";
import { useAuth } from "../auth/AuthContext";

export default function ItemTypeManager() {
  const queryClient = useQueryClient();
  const { data: itemTypes, isLoading } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Item Types</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Type
        </button>
      </div>

      <p className="mt-2 text-sm text-gray-500">
        Define item types and their custom attributes.
      </p>

      {isLoading ? (
        <div className="mt-8 flex justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      ) : (
        <div className="mt-6 space-y-2">
          {itemTypes?.map((t) => (
            <ItemTypeCard
              key={t.id}
              itemType={t}
              expanded={expandedId === t.id}
              onToggle={() =>
                setExpandedId(expandedId === t.id ? null : t.id)
              }
            />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateItemTypeDialog
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["itemTypes"] });
            setShowCreate(false);
          }}
        />
      )}
    </div>
  );
}

function ItemTypeCard({
  itemType,
  expanded,
  onToggle,
}: {
  itemType: ItemType;
  expanded: boolean;
  onToggle: () => void;
}) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [showAddField, setShowAddField] = useState(false);
  const [newField, setNewField] = useState({
    name: "",
    slug: "",
    field_kind: "text",
    is_required: false,
    options: {} as Record<string, unknown>,
  });
  const [choices, setChoices] = useState("");

  const addFieldMutation = useMutation({
    mutationFn: () => {
      const payload = { ...newField };
      if (newField.field_kind === "choice" && choices) {
        payload.options = {
          choices: choices.split(",").map((c) => c.trim()),
        };
      }
      return addCustomField(itemType.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["itemTypes"] });
      setShowAddField(false);
      setNewField({
        name: "",
        slug: "",
        field_kind: "text",
        is_required: false,
        options: {},
      });
      setChoices("");
    },
  });

  const deleteFieldMutation = useMutation({
    mutationFn: (fieldId: string) =>
      deleteCustomField(itemType.id, fieldId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["itemTypes"] });
    },
  });

  const deleteTypeMutation = useMutation({
    mutationFn: () => deleteItemType(itemType.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["itemTypes"] });
    },
  });

  const canDelete = user?.vault_role && user.vault_role !== "viewer" && itemType.item_count === 0;
  const deleteTitle =
    itemType.item_count > 0
      ? `Cannot delete: ${itemType.item_count} item${itemType.item_count !== 1 ? "s" : ""} of this type exist`
      : "Delete item type";

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <div className="flex w-full items-center gap-3 px-4 py-3">
        <button
          onClick={onToggle}
          className="flex flex-1 items-center gap-3 text-left"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <span className="font-medium text-gray-900">{itemType.name}</span>
          <span className="text-sm text-gray-500">({itemType.slug})</span>
          <span className="text-xs text-gray-400">
            {itemType.custom_fields.length} field
            {itemType.custom_fields.length !== 1 ? "s" : ""}
          </span>
          <span className="text-xs text-gray-400">
            · {itemType.item_count} item
            {itemType.item_count !== 1 ? "s" : ""}
          </span>
        </button>
        {user?.vault_role && user.vault_role !== "viewer" && (
          <button
            onClick={() => {
              if (canDelete && confirm(`Delete item type "${itemType.name}"?`))
                deleteTypeMutation.mutate();
            }}
            disabled={!canDelete || deleteTypeMutation.isPending}
            title={deleteTitle}
            className="rounded p-1 text-red-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>

      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3">
          {itemType.description && (
            <p className="mb-3 text-sm text-gray-500">
              {itemType.description}
            </p>
          )}

          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Custom Fields
          </h4>

          {itemType.custom_fields.length === 0 ? (
            <p className="mt-2 text-sm text-gray-400">
              No custom fields defined.
            </p>
          ) : (
            <table className="mt-2 w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500">
                  <th className="pb-1">Name</th>
                  <th className="pb-1">Slug</th>
                  <th className="pb-1">Type</th>
                  <th className="pb-1">Required</th>
                  <th className="pb-1"></th>
                </tr>
              </thead>
              <tbody>
                {itemType.custom_fields.map((f) => (
                  <tr key={f.id} className="border-t border-gray-50">
                    <td className="py-1.5">{f.name}</td>
                    <td className="py-1.5 text-gray-500">{f.slug}</td>
                    <td className="py-1.5">{f.field_kind}</td>
                    <td className="py-1.5">
                      {f.is_required ? "Yes" : "No"}
                    </td>
                    <td className="py-1.5">
                      <button
                        onClick={() => {
                          if (confirm(`Delete field "${f.name}"?`))
                            deleteFieldMutation.mutate(f.id);
                        }}
                        className="text-red-400 hover:text-red-600"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {!showAddField ? (
            <button
              onClick={() => setShowAddField(true)}
              className="mt-3 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Field
            </button>
          ) : (
            <div className="mt-3 space-y-3 rounded-md border border-gray-200 bg-gray-50 p-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Name
                  </label>
                  <input
                    type="text"
                    value={newField.name}
                    onChange={(e) => {
                      setNewField({
                        ...newField,
                        name: e.target.value,
                        slug: e.target.value
                          .toLowerCase()
                          .replace(/\s+/g, "-")
                          .replace(/[^a-z0-9-]/g, ""),
                      });
                    }}
                    className="mt-1 block w-full rounded border border-gray-300 px-2 py-1 text-sm"
                    placeholder="Field name"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Type
                  </label>
                  <select
                    value={newField.field_kind}
                    onChange={(e) =>
                      setNewField({ ...newField, field_kind: e.target.value })
                    }
                    className="mt-1 block w-full rounded border border-gray-300 px-2 py-1 text-sm"
                  >
                    <option value="text">Text</option>
                    <option value="integer">Integer</option>
                    <option value="decimal">Decimal</option>
                    <option value="boolean">Boolean</option>
                    <option value="date">Date</option>
                    <option value="choice">Choice</option>
                  </select>
                </div>
              </div>

              {newField.field_kind === "choice" && (
                <div>
                  <label className="text-xs font-medium text-gray-600">
                    Choices (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={choices}
                    onChange={(e) => setChoices(e.target.value)}
                    className="mt-1 block w-full rounded border border-gray-300 px-2 py-1 text-sm"
                    placeholder="Low, Medium, High"
                  />
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={newField.is_required}
                  onChange={(e) =>
                    setNewField({ ...newField, is_required: e.target.checked })
                  }
                  className="h-3.5 w-3.5 rounded border-gray-300"
                />
                <label className="text-xs text-gray-600">Required</label>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => addFieldMutation.mutate()}
                  disabled={!newField.name || addFieldMutation.isPending}
                  className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  Add
                </button>
                <button
                  onClick={() => setShowAddField(false)}
                  className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CreateItemTypeDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: () => createItemType({ name, slug, description }),
    onSuccess: onCreated,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900">
          Create Item Type
        </h2>
        <div className="mt-4 space-y-3">
          <div>
            <label className="text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setSlug(
                  e.target.value
                    .toLowerCase()
                    .replace(/\s+/g, "-")
                    .replace(/[^a-z0-9-]/g, "")
                );
              }}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">Slug</label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name || !slug || mutation.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

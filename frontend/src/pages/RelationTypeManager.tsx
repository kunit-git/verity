import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { getRelationTypes, createRelationType, deleteRelationType } from "../api/relations";
import { getItemTypes } from "../api/items";

export default function RelationTypeManager() {
  const queryClient = useQueryClient();
  const { data: relationTypes, isLoading } = useQuery({
    queryKey: ["relationTypes"],
    queryFn: getRelationTypes,
  });

  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  const [showCreate, setShowCreate] = useState(false);
  const [kind, setKind] = useState<"composition" | "trace" | "">("");
  const [name, setName] = useState("");
  const [forwardLabel, setForwardLabel] = useState("");
  const [reverseLabel, setReverseLabel] = useState("");
  const [description, setDescription] = useState("");
  const [sourceItemType, setSourceItemType] = useState<string>("");
  const [targetItemType, setTargetItemType] = useState<string>("");

  const mutation = useMutation({
    mutationFn: () =>
      createRelationType({
        kind: kind as "composition" | "trace",
        name,
        forward_label: forwardLabel,
        reverse_label: reverseLabel,
        description,
        source_item_type: sourceItemType || null,
        target_item_type: targetItemType || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["relationTypes"] });
      setShowCreate(false);
      setKind("");
      setName("");
      setForwardLabel("");
      setReverseLabel("");
      setDescription("");
      setSourceItemType("");
      setTargetItemType("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteRelationType,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["relationTypes"] });
    },
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Relation Types</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Relation Type
        </button>
      </div>

      <p className="mt-2 text-sm text-gray-500">
        Define relation types for linking items together.
      </p>

      {showCreate && (
        <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="font-medium text-gray-900">New Relation Type</h3>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-gray-700">Kind</label>
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as "composition" | "trace" | "")}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Select...</option>
                <option value="composition">Composition</option>
                <option value="trace">Trace</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., depends_on"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">
                Forward Label
              </label>
              <input
                type="text"
                value={forwardLabel}
                onChange={(e) => setForwardLabel(e.target.value)}
                placeholder="e.g., depends on"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">
                Reverse Label
              </label>
              <input
                type="text"
                value={reverseLabel}
                onChange={(e) => setReverseLabel(e.target.value)}
                placeholder="e.g., is depended on by"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">
                Source Item Type
              </label>
              <select
                value={sourceItemType}
                onChange={(e) => setSourceItemType(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Any</option>
                {itemTypes?.map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">
                Target Item Type
              </label>
              <select
                value={targetItemType}
                onChange={(e) => setTargetItemType(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Any</option>
                {itemTypes?.map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => mutation.mutate()}
              disabled={
                !kind || !name || !forwardLabel || !reverseLabel || mutation.isPending
              }
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? "Creating..." : "Create"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="mt-8 flex justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      ) : (
        <div className="mt-6 overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Kind
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Forward Label
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Reverse Label
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Source Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Target Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Description
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {relationTypes?.map((rt) => (
                <tr key={rt.id}>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      rt.kind === "composition"
                        ? "bg-purple-50 text-purple-700"
                        : "bg-blue-50 text-blue-700"
                    }`}>
                      {rt.kind}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {rt.name}
                    {rt.is_builtin && (
                      <span className="ml-2 inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium uppercase text-gray-500">
                        built-in
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {rt.forward_label}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {rt.reverse_label}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {rt.source_item_type_name ?? "Any"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {rt.target_item_type_name ?? "Any"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {rt.description}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!rt.is_builtin && (
                      <button
                        onClick={() => {
                          if (confirm(`Delete relation type "${rt.name}"?`))
                            deleteMutation.mutate(rt.id);
                        }}
                        className="rounded p-1 text-red-500 hover:bg-red-50"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
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

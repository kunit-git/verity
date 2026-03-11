import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Loader2 } from "lucide-react";
import { getItemVersion } from "../api/items";
import { confirmRelation } from "../api/relations";
import type { NavigationRef, ItemVersion } from "../types";

interface CompareDialogProps {
  relationId: string;
  currentItemId: string;
  ref_: NavigationRef;
  side: "left" | "right";
  onClose: () => void;
  onConfirmed: () => void;
}

export default function CompareDialog({
  relationId,
  currentItemId,
  ref_,
  side,
  onClose,
  onConfirmed,
}: CompareDialogProps) {
  // Determine which versions belong to which side of the relation
  // Left panel (incoming): current item = target. pinned_version → source, self_pinned_version → target
  // Right panel (outgoing): current item = source. pinned_version → target, self_pinned_version → source
  const otherItemId = ref_.id;
  const otherPinnedVersion = ref_.pinned_version ?? ref_.current_version ?? 1;
  const otherCurrentVersion = ref_.current_version ?? 1;
  const selfPinnedVersion = ref_.self_pinned_version ?? ref_.self_current_version ?? 1;
  const selfCurrentVersion = ref_.self_current_version ?? 1;

  const [otherSelectedVersion, setOtherSelectedVersion] = useState(otherCurrentVersion);
  const [selfSelectedVersion, setSelfSelectedVersion] = useState(selfCurrentVersion);
  const [submitting, setSubmitting] = useState(false);

  // Fetch pinned (old) version for other item
  const { data: otherOldData, isLoading: loadingOtherOld } = useQuery({
    queryKey: ["version", otherItemId, otherPinnedVersion],
    queryFn: () => getItemVersion(otherItemId, otherPinnedVersion),
    enabled: !!ref_.other_changed,
  });

  // Fetch selected (new) version for other item
  const { data: otherNewData, isLoading: loadingOtherNew } = useQuery({
    queryKey: ["version", otherItemId, otherSelectedVersion],
    queryFn: () => getItemVersion(otherItemId, otherSelectedVersion),
    enabled: !!ref_.other_changed,
  });

  // Fetch pinned (old) version for self item
  const { data: selfOldData, isLoading: loadingSelfOld } = useQuery({
    queryKey: ["version", currentItemId, selfPinnedVersion],
    queryFn: () => getItemVersion(currentItemId, selfPinnedVersion),
    enabled: !!ref_.self_changed,
  });

  // Fetch selected (new) version for self item
  const { data: selfNewData, isLoading: loadingSelfNew } = useQuery({
    queryKey: ["version", currentItemId, selfSelectedVersion],
    queryFn: () => getItemVersion(currentItemId, selfSelectedVersion),
    enabled: !!ref_.self_changed,
  });

  const isLoading = loadingOtherOld || loadingOtherNew || loadingSelfOld || loadingSelfNew;

  async function handleKeepOriginal() {
    setSubmitting(true);
    try {
      // Keep current pinned versions, mark as explicitly pinned
      const payload = side === "left"
        ? { source_version: otherPinnedVersion, target_version: selfPinnedVersion, version_pinned: true }
        : { source_version: selfPinnedVersion, target_version: otherPinnedVersion, version_pinned: true };
      await confirmRelation(relationId, payload);
      onConfirmed();
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdateVersion() {
    setSubmitting(true);
    try {
      const payload = side === "left"
        ? { source_version: otherSelectedVersion, target_version: selfSelectedVersion, version_pinned: false }
        : { source_version: selfSelectedVersion, target_version: otherSelectedVersion, version_pinned: false };
      await confirmRelation(relationId, payload);
      onConfirmed();
    } finally {
      setSubmitting(false);
    }
  }

  const updateLabel =
    otherSelectedVersion === otherCurrentVersion && selfSelectedVersion === selfCurrentVersion
      ? "Update to current"
      : `Update to v${ref_.other_changed ? otherSelectedVersion : selfSelectedVersion}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-3xl rounded-lg bg-white shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Compare Versions</h2>
            <p className="mt-0.5 text-sm text-gray-500">
              {ref_.relation_label} &middot; {ref_.title}
            </p>
          </div>
          <button onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <>
              {ref_.other_changed && (
                <VersionComparisonSection
                  label={`Linked item: ${ref_.title}`}
                  oldVersion={otherOldData}
                  newVersion={otherNewData}
                  pinnedVersion={otherPinnedVersion}
                  currentVersion={otherCurrentVersion}
                  selectedVersion={otherSelectedVersion}
                  onSelectVersion={setOtherSelectedVersion}
                />
              )}
              {ref_.self_changed && (
                <VersionComparisonSection
                  label="This item"
                  oldVersion={selfOldData}
                  newVersion={selfNewData}
                  pinnedVersion={selfPinnedVersion}
                  currentVersion={selfCurrentVersion}
                  selectedVersion={selfSelectedVersion}
                  onSelectVersion={setSelfSelectedVersion}
                />
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-gray-200 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
          <button
            onClick={handleKeepOriginal}
            disabled={submitting}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Keep Original Version
          </button>
          <button
            onClick={handleUpdateVersion}
            disabled={submitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Updating..." : updateLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function VersionComparisonSection({
  label,
  oldVersion,
  newVersion,
  pinnedVersion,
  currentVersion,
  selectedVersion,
  onSelectVersion,
}: {
  label: string;
  oldVersion?: ItemVersion;
  newVersion?: ItemVersion;
  pinnedVersion: number;
  currentVersion: number;
  selectedVersion: number;
  onSelectVersion: (v: number) => void;
}) {
  // Build version options from pinned+1 through current
  const versionOptions: number[] = [];
  for (let v = pinnedVersion + 1; v <= currentVersion; v++) {
    versionOptions.push(v);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-800">{label}</h3>
        {versionOptions.length > 1 && (
          <select
            value={selectedVersion}
            onChange={(e) => onSelectVersion(Number(e.target.value))}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            {versionOptions.map((v) => (
              <option key={v} value={v}>
                v{v}{v === currentVersion ? " (current)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="text-xs font-medium text-gray-500 mb-1">
          v{pinnedVersion} (linked)
        </div>
        <div className="text-xs font-medium text-gray-500 mb-1">
          v{selectedVersion}{selectedVersion === currentVersion ? " (current)" : ""}
        </div>
      </div>

      {/* Compare fields */}
      <FieldComparison label="Title" oldVal={oldVersion?.title} newVal={newVersion?.title} />
      <FieldComparison label="Description" oldVal={oldVersion?.description} newVal={newVersion?.description} />
      <FieldComparison label="Status" oldVal={oldVersion?.status} newVal={newVersion?.status} />

      {/* Custom fields */}
      {(oldVersion?.custom_fields_snapshot || newVersion?.custom_fields_snapshot) && (
        <CustomFieldsComparison
          oldFields={oldVersion?.custom_fields_snapshot || {}}
          newFields={newVersion?.custom_fields_snapshot || {}}
        />
      )}
    </div>
  );
}

function FieldComparison({
  label,
  oldVal,
  newVal,
}: {
  label: string;
  oldVal?: string;
  newVal?: string;
}) {
  const changed = oldVal !== newVal;
  return (
    <div className={`grid grid-cols-2 gap-4 rounded-md px-2 py-1.5 ${changed ? "bg-amber-50" : ""}`}>
      <div>
        <span className="text-xs font-medium text-gray-500">{label}</span>
        <p className="text-sm text-gray-800 whitespace-pre-wrap">{oldVal || "—"}</p>
      </div>
      <div>
        <span className="text-xs font-medium text-gray-500">{label}</span>
        <p className={`text-sm whitespace-pre-wrap ${changed ? "text-amber-800 font-medium" : "text-gray-800"}`}>
          {newVal || "—"}
        </p>
      </div>
    </div>
  );
}

function CustomFieldsComparison({
  oldFields,
  newFields,
}: {
  oldFields: Record<string, unknown>;
  newFields: Record<string, unknown>;
}) {
  const allKeys = [...new Set([...Object.keys(oldFields), ...Object.keys(newFields)])];
  if (allKeys.length === 0) return null;

  return (
    <>
      {allKeys.map((key) => (
        <FieldComparison
          key={key}
          label={key}
          oldVal={String(oldFields[key] ?? "—")}
          newVal={String(newFields[key] ?? "—")}
        />
      ))}
    </>
  );
}

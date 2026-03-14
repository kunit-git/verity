import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Compass, ArrowRight } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import * as vaultsApi from "../api/vaults";

export default function VaultSelectorPage() {
  const { user, selectVault, logout } = useAuth();
  const navigate = useNavigate();
  const [selecting, setSelecting] = useState<string | null>(null);
  const [error, setError] = useState("");

  const { data: vaults, isLoading } = useQuery({
    queryKey: ["my-vaults"],
    queryFn: vaultsApi.getMyVaults,
  });

  const handleSelect = async (vaultId: string) => {
    setSelecting(vaultId);
    setError("");
    try {
      await selectVault(vaultId);
      navigate("/");
    } catch {
      setError("Failed to select vault.");
      setSelecting(null);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-lg px-4">
        <div className="mb-8 text-center">
          <Compass className="mx-auto h-10 w-10 text-blue-600" />
          <h1 className="mt-3 text-2xl font-bold text-gray-900">Select a Vault</h1>
          <p className="mt-1 text-sm text-gray-500">
            Choose a workspace to continue
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          </div>
        ) : !vaults?.length ? (
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
            <p className="text-gray-500">No vaults available.</p>
            <p className="mt-1 text-sm text-gray-400">
              Contact an administrator to get access.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {vaults.map((vault) => (
              <button
                key={vault.id}
                onClick={() => handleSelect(vault.id)}
                disabled={selecting !== null}
                className="flex w-full items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 text-left transition hover:border-blue-300 hover:bg-blue-50 disabled:opacity-60"
              >
                <div>
                  <p className="font-medium text-gray-900">{vault.name}</p>
                  {vault.description && (
                    <p className="mt-0.5 text-sm text-gray-500">{vault.description}</p>
                  )}
                </div>
                {selecting === vault.id ? (
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
                ) : (
                  <ArrowRight className="h-5 w-5 text-gray-400" />
                )}
              </button>
            ))}
          </div>
        )}

        <div className="mt-6 text-center">
          <span className="text-sm text-gray-500">
            Signed in as <span className="font-medium">{user?.username}</span>
          </span>
          <button
            onClick={logout}
            className="ml-2 text-sm text-blue-600 hover:text-blue-800"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

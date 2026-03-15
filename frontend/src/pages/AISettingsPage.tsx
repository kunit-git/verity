import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, Save, Eye, EyeOff, CheckCircle, AlertCircle, RefreshCw } from "lucide-react";
import { getSiteSettings, updateSiteSettings } from "../api/users";
import { fetchAvailableModels } from "../api/agent";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmDialog";
import { useNavigate } from "react-router-dom";

export default function AISettingsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();

  useEffect(() => {
    if (user && !user.is_site_admin) navigate("/");
  }, [user, navigate]);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["site-settings"],
    queryFn: getSiteSettings,
  });

  const [aiEnabled, setAiEnabled] = useState(false);
  const [providerType, setProviderType] = useState<"openai" | "anthropic" | "">("");
  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  useEffect(() => {
    if (settings) {
      setAiEnabled(settings.ai_enabled);
      setProviderType(settings.ai_provider_type);
      setApiUrl(settings.ai_api_url ?? "");
      setModel(settings.ai_model ?? "");
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: updateSiteSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["site-settings"] });
      queryClient.invalidateQueries({ queryKey: ["agent-status"] });
      setSaved(true);
      setApiKey("");
      setTimeout(() => setSaved(false), 3000);
    },
    onError: async (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "An unexpected error occurred while saving.";
      await confirm({
        title: "Save failed",
        message: detail,
        confirmLabel: "OK",
        cancelLabel: "",
        destructive: false,
      });
    },
  });

  const handleLoadModels = async () => {
    setLoadingModels(true);
    try {
      const models = await fetchAvailableModels({
        ai_provider_type: providerType || undefined,
        ai_api_url: apiUrl || undefined,
        ai_api_key: apiKey || undefined,
      });
      setAvailableModels(models);
      // If current model is not in the list, clear it
      if (model && !models.includes(model)) setModel("");
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? String(err);
      await confirm({
        title: "Failed to load models",
        message: `Could not fetch available models from the provider.\n\n${detail}`,
        confirmLabel: "OK",
        cancelLabel: "",
        destructive: false,
      });
    } finally {
      setLoadingModels(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const patch: Parameters<typeof updateSiteSettings>[0] = {
      ai_enabled: aiEnabled,
      ai_provider_type: providerType,
      ai_api_url: apiUrl,
      ai_model: model,
    };
    if (apiKey) patch.ai_api_key = apiKey;
    saveMutation.mutate(patch);
  };

  if (!user?.is_site_admin) return null;
  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-sm text-gray-500">Loading…</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8">
      <div className="mb-6 flex items-center gap-3">
        <Bot className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-xl font-semibold text-gray-900">AI Settings</h1>
          <p className="text-sm text-gray-500">
            Configure the AI assistant provider for this site.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Enable toggle */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">Enable AI Assistant</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Show the AI Assistant to all users in the application.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setAiEnabled((v) => !v)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                aiEnabled ? "bg-blue-600" : "bg-gray-200"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  aiEnabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-5">
          <h2 className="text-sm font-semibold text-gray-900">Provider Configuration</h2>

          {/* 1. Provider */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Provider
            </label>
            <div className="flex gap-3">
              {(["anthropic", "openai"] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    setProviderType(p);
                    setModel("");
                    setAvailableModels([]);
                  }}
                  className={`flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                    providerType === p
                      ? "border-blue-600 bg-blue-50 text-blue-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {p === "anthropic" ? "Anthropic" : "OpenAI"}
                </button>
              ))}
            </div>
          </div>

          {/* 2. Custom base URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Custom API Base URL
              <span className="ml-1 text-xs font-normal text-gray-400">(optional)</span>
            </label>
            <input
              type="url"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="e.g. https://my-azure-endpoint.openai.azure.com/v1"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-400">
              Leave blank to use the default endpoint. Use this for Azure OpenAI, proxies, or self-hosted models.
            </p>
          </div>

          {/* 3. API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              API Key
            </label>
            <div className="relative">
              <input
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  settings?.ai_api_key_set
                    ? "Key already set — enter a new one to replace it"
                    : "Enter your API key"
                }
                className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {settings?.ai_api_key_set && !apiKey && (
              <p className="mt-1 flex items-center gap-1 text-xs text-green-600">
                <CheckCircle className="h-3 w-3" /> API key is configured. Leave blank to keep it.
              </p>
            )}
          </div>

          {/* 4. Model — dropdown + reload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Model
            </label>
            <div className="flex gap-2">
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
                disabled={availableModels.length === 0}
              >
                {availableModels.length === 0 ? (
                  <option value={model}>{model || "— load models first —"}</option>
                ) : (
                  <>
                    <option value="">— select a model —</option>
                    {availableModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </>
                )}
              </select>
              <button
                type="button"
                onClick={handleLoadModels}
                disabled={loadingModels || !providerType || (!apiKey && !settings?.ai_api_key_set)}
                title="Fetch available models from provider"
                className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <RefreshCw
                  className={`h-4 w-4 ${loadingModels ? "animate-spin" : ""}`}
                />
                {loadingModels ? "Loading…" : "Load"}
              </button>
            </div>
            <p className="mt-1 text-xs text-gray-400">
              Click Load to fetch the list of available models from the configured provider.
            </p>
          </div>
        </div>

        {/* Warning: enabled but no key */}
        {!settings?.ai_api_key_set && !apiKey && aiEnabled && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertCircle className="h-4 w-4 shrink-0" />
            An API key is required before users can use the AI assistant.
          </div>
        )}

        {/* Save */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving…" : "Save Settings"}
          </button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-green-600">
              <CheckCircle className="h-4 w-4" /> Saved
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

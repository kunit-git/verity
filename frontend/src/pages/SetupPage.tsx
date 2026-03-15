import { useState } from "react";
import { Compass } from "lucide-react";
import { performSetup, login } from "../api/auth";

export default function SetupPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    if (password !== confirm) {
      setErrors({ confirm: "Passwords do not match." });
      return;
    }

    setSubmitting(true);
    try {
      await performSetup(username, password);
      await login(username, password);
      // Full reload so SetupGuard re-evaluates setup status.
      window.location.replace("/");
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, unknown> } })
        .response?.data;
      if (data && typeof data === "object") {
        const mapped: Record<string, string> = {};
        for (const [k, v] of Object.entries(data)) {
          mapped[k] = Array.isArray(v) ? (v[0] as string) : String(v);
        }
        setErrors(mapped);
      } else {
        setErrors({ detail: "An unexpected error occurred. Please try again." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <Compass className="mx-auto h-10 w-10 text-blue-600" />
          <h1 className="mt-3 text-2xl font-bold text-gray-900">
            Welcome to Verity
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Create the initial administrator account to get started.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {errors.detail && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {errors.detail}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {errors.username && (
              <p className="mt-1 text-xs text-red-600">{errors.username}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">{errors.password}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Confirm password
            </label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {errors.confirm && (
              <p className="mt-1 text-xs text-red-600">{errors.confirm}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Creating account..." : "Create administrator account"}
          </button>
        </form>
      </div>
    </div>
  );
}

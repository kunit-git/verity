import { useState, useEffect, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { checkSetupStatus } from "../api/auth";

type Status = "loading" | "ok" | "setup_required" | "db_error";

function SystemErrorPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
          <svg
            className="h-7 w-7 text-red-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01M12 3a9 9 0 100 18A9 9 0 0012 3z"
            />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-gray-900">System Error</h1>
        <p className="mt-2 text-sm text-gray-600">
          The system is temporarily unavailable. Please wait a moment and try
          again.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-6 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

export default function SetupGuard({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const location = useLocation();

  useEffect(() => {
    checkSetupStatus()
      .then((res) => {
        setStatus(res.setup_required ? "setup_required" : "ok");
      })
      .catch((err) => {
        if (err.response?.status === 503) {
          setStatus("db_error");
        } else {
          // On unexpected errors assume the system is operational to avoid
          // locking users out due to transient issues.
          setStatus("ok");
        }
      });
  }, []);

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (status === "db_error") {
    return <SystemErrorPage />;
  }

  if (status === "setup_required" && location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }

  return <>{children}</>;
}

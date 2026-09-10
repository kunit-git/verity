import { createContext, useContext, useState, useCallback, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

type ConfirmFn = (options: ConfirmOptions | string) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

// Consumer hook shares the component module; edits may trigger a full reload.
// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm(): ConfirmFn {
  const fn = useContext(ConfirmContext);
  if (!fn) throw new Error("useConfirm must be used within ConfirmProvider");
  return fn;
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<(ConfirmOptions & { open: boolean }) | null>(null);
  const resolveRef = useRef<((v: boolean) => void) | null>(null);

  const confirm: ConfirmFn = useCallback((options) => {
    const opts = typeof options === "string" ? { message: options } : options;
    setState({ ...opts, open: true });
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  const handleClose = (result: boolean) => {
    setState(null);
    resolveRef.current?.(result);
    resolveRef.current = null;
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {state?.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
              <div className="flex items-center gap-2">
                {state.destructive !== false && (
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                )}
                <h2 className="text-sm font-semibold text-gray-900">
                  {state.title ?? "Confirm"}
                </h2>
              </div>
              <button
                onClick={() => handleClose(false)}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="px-4 py-4">
              <p className="text-sm text-gray-600">{state.message}</p>
            </div>

            <div className="flex gap-2 border-t border-gray-100 px-4 py-3">
              <button
                onClick={() => handleClose(false)}
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                {state.cancelLabel ?? "Cancel"}
              </button>
              <button
                onClick={() => handleClose(true)}
                autoFocus
                className={`flex-1 rounded-md px-3 py-2 text-sm font-medium text-white ${
                  state.destructive === false
                    ? "bg-blue-600 hover:bg-blue-700"
                    : "bg-red-600 hover:bg-red-700"
                }`}
              >
                {state.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

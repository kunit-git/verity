import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X } from "lucide-react";
import { changeOwnPassword, adminChangePassword } from "../api/users";

interface Props {
  /** If set, admin is changing another user's password */
  targetUser?: { id: number; username: string } | null;
  onClose: () => void;
}

export default function ChangePasswordDialog({ targetUser, onClose }: Props) {
  const isOwnPassword = !targetUser;

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      if (isOwnPassword) {
        return changeOwnPassword(currentPassword, newPassword);
      }
      return adminChangePassword(targetUser!.id, newPassword);
    },
    onSuccess: () => {
      setSuccess(true);
      setError("");
    },
    onError: (err: any) => {
      const data = err?.response?.data;
      if (data?.current_password) {
        setError(data.current_password[0]);
      } else if (data?.new_password) {
        setError(data.new_password[0]);
      } else {
        setError("Failed to change password.");
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    mutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-900">
            {isOwnPassword
              ? "Change Password"
              : `Set Password for ${targetUser!.username}`}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {success ? (
          <div className="p-4">
            <p className="text-sm text-green-600">
              Password changed successfully.
            </p>
            <button
              onClick={onClose}
              className="mt-3 w-full rounded-md bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-4 space-y-3">
            {isOwnPassword && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Current Password
                </label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Confirm New Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="flex-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {mutation.isPending ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

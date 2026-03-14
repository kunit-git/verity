import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function VaultGuard() {
  const { user } = useAuth();

  if (!user?.active_vault) {
    return <Navigate to="/vaults/select" replace />;
  }

  return <Outlet />;
}

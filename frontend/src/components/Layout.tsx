import { useState } from "react";
import { Outlet, Link, useLocation, useMatch, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import CompositionTree from "./CompositionTree";
import ChangePasswordDialog from "./ChangePasswordDialog";
import {
  LayoutDashboard,
  List,
  Plus,
  Settings,
  LogOut,
  Compass,
  Table2,
  Users,
  FileText,
  Inbox,
  KeyRound,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronDown,
  Vault,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import * as vaultsApi from "../api/vaults";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/items", icon: List, label: "All Items" },
  { to: "/items/new", icon: Plus, label: "New Item" },
];

const adminItems = [
  { to: "/manage/item-types", icon: Settings, label: "Item Types" },
  { to: "/manage/relation-types", icon: Settings, label: "Relation Types" },
  { to: "/manage/templates", icon: FileText, label: "Doc Templates" },
];

const superAdminItems = [
  { to: "/manage/users", icon: Users, label: "Users" },
  { to: "/manage/vaults", icon: Vault, label: "Vaults" },
];

export default function Layout() {
  const { user, logout, selectVault } = useAuth();
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showVaultDropdown, setShowVaultDropdown] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const itemMatch = useMatch("/items/:id");
  const editMatch = useMatch("/items/:id/edit");
  const showTree = !!itemMatch && !editMatch;
  const currentItemId = itemMatch?.params.id;

  const { data: myVaults } = useQuery({
    queryKey: ["my-vaults"],
    queryFn: vaultsApi.getMyVaults,
  });

  const handleVaultSwitch = async (vaultId: string) => {
    setShowVaultDropdown(false);
    await selectVault(vaultId);
    navigate("/");
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className={`flex flex-col border-r border-gray-200 bg-white transition-all duration-200 ${collapsed ? "w-14" : "w-64"}`}>
        <div className={`flex h-14 items-center border-b border-gray-200 px-2 ${collapsed ? "justify-center" : "justify-between px-4"}`}>
          {!collapsed && (
            <div className="flex items-center gap-2">
              <Compass className="h-6 w-6 text-blue-600" />
              <span className="text-lg font-bold text-gray-900">Verity</span>
            </div>
          )}
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          </button>
        </div>

        {/* Vault switcher */}
        {!collapsed && user?.active_vault_name && (
          <div className="relative border-b border-gray-200 px-3 py-2">
            <button
              onClick={() => setShowVaultDropdown((v) => !v)}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-gray-100"
            >
              <span className="truncate font-medium text-gray-700">{user.active_vault_name}</span>
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gray-400" />
            </button>
            {showVaultDropdown && (
              <div className="absolute left-2 right-2 top-full z-50 mt-1 rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                {myVaults?.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => handleVaultSwitch(v.id)}
                    className={`flex w-full items-center px-3 py-2 text-sm hover:bg-gray-100 ${
                      v.id === user.active_vault ? "bg-blue-50 text-blue-700" : "text-gray-700"
                    }`}
                  >
                    {v.name}
                  </button>
                ))}
                <div className="border-t border-gray-100 pt-1">
                  <button
                    onClick={() => { setShowVaultDropdown(false); navigate("/vaults/select"); }}
                    className="flex w-full items-center px-3 py-2 text-sm text-gray-500 hover:bg-gray-100"
                  >
                    All vaults...
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
        {collapsed && user?.active_vault_name && (
          <div className="border-b border-gray-200 px-2 py-2">
            <button
              onClick={() => navigate("/vaults/select")}
              className="flex w-full justify-center rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              title={user.active_vault_name}
            >
              <Vault className="h-4 w-4" />
            </button>
          </div>
        )}

        <nav className="flex-1 overflow-y-auto p-2">
          <div className="space-y-1">
            {navItems.map((item) => {
              const active = location.pathname === item.to;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  title={collapsed ? item.label : undefined}
                  className={`flex items-center rounded-md px-2 py-2 text-sm font-medium transition-colors ${collapsed ? "justify-center" : "gap-2"} ${
                    active
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <item.icon className="h-4 w-4 shrink-0" />
                  {!collapsed && item.label}
                </Link>
              );
            })}
          </div>

          {/* Analysis section */}
          <div className="mt-4">
            {!collapsed && (
              <h3 className="px-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Analysis
              </h3>
            )}
            <div className="mt-1 space-y-1">
              <Link
                to="/tables"
                title={collapsed ? "Tables" : undefined}
                className={`flex items-center rounded-md px-2 py-2 text-sm font-medium transition-colors ${collapsed ? "justify-center" : "gap-2"} ${
                  location.pathname.startsWith("/tables")
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Table2 className="h-4 w-4 shrink-0" />
                {!collapsed && "Tables"}
              </Link>
            </div>
          </div>

          {/* Mailbox */}
          <div className="mt-4">
            {!collapsed && (
              <h3 className="px-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Documents
              </h3>
            )}
            <div className="mt-1 space-y-1">
              <Link
                to="/mailbox"
                title={collapsed ? "Mailbox" : undefined}
                className={`flex items-center rounded-md px-2 py-2 text-sm font-medium transition-colors ${collapsed ? "justify-center" : "gap-2"} ${
                  location.pathname === "/mailbox"
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Inbox className="h-4 w-4 shrink-0" />
                {!collapsed && "Mailbox"}
              </Link>
            </div>
          </div>

          {/* Admin section */}
          <div className="mt-4">
            {!collapsed && (
              <h3 className="px-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Manage
              </h3>
            )}
            <div className="mt-1 space-y-1">
              {[...adminItems, ...(user?.is_site_admin ? superAdminItems : [])].map((item) => {
                const active = location.pathname === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    title={collapsed ? item.label : undefined}
                    className={`flex items-center rounded-md px-2 py-2 text-sm font-medium transition-colors ${collapsed ? "justify-center" : "gap-2"} ${
                      active
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {!collapsed && item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </nav>

        {/* User section */}
        <div className="border-t border-gray-200 p-2">
          {collapsed ? (
            <div className="flex flex-col items-center gap-1">
              <button
                onClick={() => setShowPasswordDialog(true)}
                className="rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                title="Change password"
              >
                <KeyRound className="h-4 w-4" />
              </button>
              <button
                onClick={logout}
                className="rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                title="Logout"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900">
                  {user?.username}
                </p>
                <p className="text-xs text-gray-500">{user?.vault_role}{user?.is_site_admin ? " · site admin" : ""}</p>
              </div>
              <div className="flex gap-0.5">
                <button
                  onClick={() => setShowPasswordDialog(true)}
                  className="rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                  title="Change password"
                >
                  <KeyRound className="h-4 w-4" />
                </button>
                <button
                  onClick={logout}
                  className="rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                  title="Logout"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Composition tree */}
      {showTree && <CompositionTree currentItemId={currentItemId} />}

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>

      {showPasswordDialog && (
        <ChangePasswordDialog onClose={() => setShowPasswordDialog(false)} />
      )}
    </div>
  );
}

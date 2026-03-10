import { useState } from "react";
import { Outlet, Link, useLocation, useMatch } from "react-router-dom";
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
  Inbox,
  KeyRound,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/items", icon: List, label: "All Items" },
  { to: "/items/new", icon: Plus, label: "New Item" },
];

const adminItems = [
  { to: "/manage/item-types", icon: Settings, label: "Item Types" },
  { to: "/manage/relation-types", icon: Settings, label: "Relation Types" },
];

const superAdminItems = [
  { to: "/manage/users", icon: Users, label: "Users" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const itemMatch = useMatch("/items/:id");
  const editMatch = useMatch("/items/:id/edit");
  const showTree = !!itemMatch && !editMatch;
  const currentItemId = itemMatch?.params.id;
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
              {[...adminItems, ...(user?.role === "admin" ? superAdminItems : [])].map((item) => {
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
                <p className="text-xs text-gray-500">{user?.role}</p>
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

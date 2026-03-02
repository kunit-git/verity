import { useState } from "react";
import { Outlet, Link, useLocation, useMatch } from "react-router-dom";
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
  ChevronRight,
  Table2,
  Users,
  Inbox,
  KeyRound,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { getItemTypes } from "../api/items";

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
  const location = useLocation();
  const itemMatch = useMatch("/items/:id");
  const editMatch = useMatch("/items/:id/edit");
  const showTree = !!itemMatch && !editMatch;
  const currentItemId = itemMatch?.params.id;
  const { data: itemTypes } = useQuery({
    queryKey: ["itemTypes"],
    queryFn: getItemTypes,
  });

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-gray-200 bg-white">
        <div className="flex h-14 items-center gap-2 border-b border-gray-200 px-4">
          <Compass className="h-6 w-6 text-blue-600" />
          <span className="text-lg font-bold text-gray-900">Verity</span>
        </div>

        <nav className="flex-1 overflow-y-auto p-3">
          <div className="space-y-1">
            {navItems.map((item) => {
              const active = location.pathname === item.to;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Item types as quick filters */}
          {itemTypes && itemTypes.length > 0 && (
            <div className="mt-6">
              <h3 className="px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                By Type
              </h3>
              <div className="mt-2 space-y-1">
                {[...itemTypes].sort((a, b) => a.name.localeCompare(b.name)).map((t) => (
                  <Link
                    key={t.id}
                    to={`/items?type=${t.slug}`}
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-600 hover:bg-gray-100"
                  >
                    <ChevronRight className="h-3 w-3" />
                    {t.name}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Analysis section */}
          <div className="mt-6">
            <h3 className="px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Analysis
            </h3>
            <div className="mt-2 space-y-1">
              <Link
                to="/tables"
                className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  location.pathname.startsWith("/tables")
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Table2 className="h-4 w-4" />
                Tables
              </Link>
            </div>
          </div>

          {/* Mailbox */}
          <div className="mt-6">
            <h3 className="px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Documents
            </h3>
            <div className="mt-2 space-y-1">
              <Link
                to="/mailbox"
                className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  location.pathname === "/mailbox"
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Inbox className="h-4 w-4" />
                Mailbox
              </Link>
            </div>
          </div>

          {/* Admin section */}
          <div className="mt-6">
            <h3 className="px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
              Manage
            </h3>
            <div className="mt-2 space-y-1">
              {[...adminItems, ...(user?.role === "admin" ? superAdminItems : [])].map((item) => {
                const active = location.pathname === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      active
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </nav>

        {/* User section */}
        <div className="border-t border-gray-200 p-3">
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

import { Routes, Route, useParams } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";
import SetupGuard from "./auth/SetupGuard";
import VaultGuard from "./components/VaultGuard";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import SetupPage from "./pages/SetupPage";
import VaultSelectorPage from "./pages/VaultSelectorPage";
import DashboardPage from "./pages/DashboardPage";
import ItemListPage from "./pages/ItemListPage";
import ItemCreatePage from "./pages/ItemCreatePage";
import ItemNavigator from "./pages/ItemNavigator";
import ItemTypeManager from "./pages/ItemTypeManager";
import RelationTypeManager from "./pages/RelationTypeManager";
import UserManagementPage from "./pages/UserManagementPage";
import VaultManagementPage from "./pages/VaultManagementPage";
import VaultAuditLogPage from "./pages/VaultAuditLogPage";
import TableListPage from "./pages/TableListPage";
import TableEditorPage from "./pages/TableEditorPage";
import TableViewPage from "./pages/TableViewPage";
import MailboxPage from "./pages/MailboxPage";
import DocumentTemplateManager from "./pages/DocumentTemplateManager";
import AISettingsPage from "./pages/AISettingsPage";
import DocumentEditorPage from "./pages/DocumentEditorPage";

function ItemEditWrapper() {
  const { id } = useParams<{ id: string }>();
  return <ItemCreatePage editId={id} />;
}

export default function App() {
  return (
    <SetupGuard>
      <Routes>
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/vaults/select" element={<VaultSelectorPage />} />

          <Route element={<VaultGuard />}>
            <Route element={<Layout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/items" element={<ItemListPage />} />
              <Route path="/items/new" element={<ItemCreatePage />} />
              <Route path="/items/:id" element={<ItemNavigator />} />
              <Route path="/items/:id/edit" element={<ItemEditWrapper />} />
              <Route path="/items/:id/doc-edit" element={<DocumentEditorPage />} />
              <Route path="/manage/item-types" element={<ItemTypeManager />} />
              <Route
                path="/manage/relation-types"
                element={<RelationTypeManager />}
              />
              <Route path="/manage/templates" element={<DocumentTemplateManager />} />
              <Route path="/manage/users" element={<UserManagementPage />} />
              <Route path="/manage/vaults" element={<VaultManagementPage />} />
              <Route path="/manage/ai" element={<AISettingsPage />} />
              <Route path="/vaults/:id/audit-log" element={<VaultAuditLogPage />} />
              <Route path="/mailbox" element={<MailboxPage />} />
              <Route path="/tables" element={<TableListPage />} />
              <Route path="/tables/new" element={<TableEditorPage />} />
              <Route path="/tables/:id" element={<TableViewPage />} />
              <Route path="/tables/:id/edit" element={<TableEditorPage />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </SetupGuard>
  );
}

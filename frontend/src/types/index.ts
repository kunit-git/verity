export interface User {
  id: number;
  username: string;
  email: string;
  is_site_admin: boolean;
  vault_role: "viewer" | "editor" | "admin" | null;
  date_joined: string;
  account_status: "active" | "locked" | "deleted";
  is_active: boolean;
  active_vault: string | null;
  active_vault_name: string | null;
  active_vault_locked: boolean;
}

export interface Vault {
  id: string;
  name: string;
  slug: string;
  description: string;
  created_by: number;
  created_by_username: string;
  member_count: number;
  is_locked: boolean;
  locked_at: string | null;
  locked_by: number | null;
  locked_by_username: string | null;
  created_at: string;
  my_role: "viewer" | "editor" | "admin" | null;
}

export interface VaultAuditLogEntry {
  id: string;
  vault: string;
  event: string;
  actor: number;
  actor_username: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface VaultMembership {
  id: string;
  vault: string;
  user: number;
  username: string;
  email: string;
  role: string;
  is_site_admin: boolean;
  created_at: string;
}

export interface CustomFieldDefinition {
  id: string;
  name: string;
  slug: string;
  field_kind: "text" | "integer" | "decimal" | "boolean" | "date" | "choice" | "mermaid" | "table";
  is_required: boolean;
  options: Record<string, unknown>;
  display_order: number;
}

// Column spec for item-embedded table fields (stored in CustomFieldDefinition.options.columns)
export type TableFieldColumnKind = "traversal" | "item_field" | "annotation" | "formula";

export interface TableFieldColumnSpec {
  name: string;
  kind: TableFieldColumnKind;
  label: string;
  relation_type_id?: string;
  direction?: "outgoing" | "incoming";
  field_slug?: string;
  source_ref?: string;
  slug?: string;
  formula?: string;
}

export interface ItemType {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  is_active: boolean;
  custom_fields: CustomFieldDefinition[];
  item_count: number;
}

export interface ItemListItem {
  id: string;
  title: string;
  status: string;
  item_type: string;
  item_type_name: string;
  item_type_slug: string;
  created_by: number;
  created_by_username: string;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface Item extends ItemListItem {
  description: string;
  custom_fields: Record<string, unknown>;
  current_version: number;
}

export interface ItemVersion {
  id: string;
  version_number: number;
  title: string;
  description: string;
  status: string;
  custom_fields_snapshot: Record<string, unknown>;
  created_by: number;
  created_by_username: string;
  created_at: string;
  change_summary: string;
}

export interface RelationType {
  id: string;
  kind: "composition" | "trace";
  name: string;
  forward_label: string;
  reverse_label: string;
  description: string;
  source_item_type: string | null;
  source_item_type_name: string | null;
  target_item_type: string | null;
  target_item_type_name: string | null;
  is_builtin: boolean;
  is_active: boolean;
}

export interface ItemRelation {
  id: string;
  relation_type: string;
  relation_type_name: string;
  forward_label: string;
  reverse_label: string;
  source: string;
  source_title: string;
  source_type_slug: string;
  source_version: number | null;
  target: string;
  target_title: string;
  target_type_slug: string;
  target_version: number | null;
  version_pinned: boolean;
  created_by: number;
  created_at: string;
}

export interface NavigationRef {
  id: string;
  title: string;
  item_type_slug: string;
  relation_id?: string;
  relation_type?: string;
  relation_label?: string;
  pinned_version?: number | null;
  current_version?: number;
  self_pinned_version?: number | null;
  self_current_version?: number | null;
  is_suspect?: boolean;
  other_changed?: boolean;
  self_changed?: boolean;
  is_version_pinned?: boolean;
}

export interface NavigationContext {
  parent: NavigationRef | null;
  children: NavigationRef[];
  siblings: NavigationRef[];
  left: NavigationRef[];
  right: NavigationRef[];
}

export interface TreeNode {
  id: string;
  title: string;
  item_type_slug: string;
  child_count: number;
  position: number;
  has_suspect_links?: boolean;
  has_suspect_descendants?: boolean;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ---- Document Templates ----

export interface DocumentTemplateResponse {
  id?: string;
  template: string | null;
  default_template: string;
  available_fields: string[];
  updated_at?: string;
}

// ---- Mailbox ----

export interface MailboxArtifact {
  id: string;
  filename: string;
  file_size: number;
  content_type: string;
  source_item: string | null;
  created_at: string;
}

export interface MailboxArtifactDetail extends MailboxArtifact {
  content: string;
}

// ---- Tables ----

export type SourceKind = "seed" | "traversal" | "formula" | "annotation" | "item_field";

export interface TableSource {
  id: string;
  name: string;
  position: number;
  kind: SourceKind;
  seed_item_type: string | null;
  seed_item_type_name: string | null;
  seed_container: string | null;
  seed_container_title: string | null;
  relation_type: string | null;
  relation_type_name: string | null;
  relation_forward_label: string | null;
  relation_reverse_label: string | null;
  direction: "outgoing" | "incoming" | null;
  formula: string | null;
  source_ref: string | null;
  field_slug: string | null;
}

export interface TableDisplayColumn {
  id: string;
  position: number;
  heading: string;
  source: string;
}

export interface Table {
  id: string;
  name: string;
  description: string;
  created_by: number;
  created_by_username: string;
  sources: TableSource[];
  columns: TableDisplayColumn[];
  created_at: string;
  updated_at: string;
}

export interface TableSourcePayload {
  name: string;
  kind: SourceKind;
  seed_item_type?: string | null;
  seed_container?: string | null;
  relation_type?: string | null;
  direction?: "outgoing" | "incoming" | null;
  formula?: string | null;
  source_ref?: string | null;
  field_slug?: string | null;
}

export interface TableDisplayColumnPayload {
  heading: string;
  source: string;
}

export interface TablePayload {
  name: string;
  description?: string;
  sources: TableSourcePayload[];
  columns: TableDisplayColumnPayload[];
}

export interface TableDataColumn {
  position: number;
  heading: string;
  source: string;
  kind: SourceKind;
  slug: string | null;
}

export interface TableDataCell {
  id: string;
  title: string;
  item_type_name: string;
  item_type_slug: string;
}

export interface TableFormulaCell {
  value: number;
}

export interface TableAnnotationCell {
  annotation: true;
  value: string;
  row_hash: string;
  column_slug: string;
}

export interface TableItemFieldCell {
  item_field: true;
  value: unknown;
}

export type AnyTableCell =
  | TableDataCell
  | TableFormulaCell
  | TableAnnotationCell
  | TableItemFieldCell
  | null;

export function isFormulaCell(cell: AnyTableCell): cell is TableFormulaCell {
  return cell !== null && "value" in cell && !("id" in cell) && !("annotation" in cell) && !("item_field" in cell);
}

export function isAnnotationCell(cell: AnyTableCell): cell is TableAnnotationCell {
  return cell !== null && (cell as TableAnnotationCell).annotation === true;
}

export function isItemFieldCell(cell: AnyTableCell): cell is TableItemFieldCell {
  return cell !== null && (cell as TableItemFieldCell).item_field === true;
}

export interface TableData {
  columns: TableDataColumn[];
  rows: AnyTableCell[][];
}

// ---- Document Editor ----

export interface EditorFieldDefinition {
  slug: string;
  name: string;
  field_kind: "text" | "integer" | "decimal" | "boolean" | "date" | "choice" | "mermaid" | "table";
  options: Record<string, unknown>;
}

export interface EditorItem {
  id: string;
  depth: number;
  title: string;
  description: string;
  status: string;
  item_type_id: string;
  item_type_name: string;
  current_version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  custom_fields: Record<string, unknown>;
  custom_field_definitions: EditorFieldDefinition[];
  template: string | null;
  default_template: string;
}

export interface DocumentEditorData {
  items: EditorItem[];
}

// ---- Agent ----

export interface AgentConversation {
  id: string;
  title: string;
  context_item: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_calls: unknown[];
  tool_call_id: string;
  tool_name: string;
  created_at: string;
}

export interface AgentPendingAction {
  id: string;
  action_type: "create_item" | "update_item" | "create_relation";
  payload: Record<string, unknown>;
  status: "pending" | "accepted" | "rejected" | "executed" | "failed";
  result: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
}

export interface AgentConversationDetail extends AgentConversation {
  messages: AgentMessage[];
  pending_actions: AgentPendingAction[];
}

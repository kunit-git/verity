export interface User {
  id: number;
  username: string;
  email: string;
  role: "viewer" | "editor" | "admin";
  date_joined: string;
}

export interface CustomFieldDefinition {
  id: string;
  name: string;
  slug: string;
  field_kind: "text" | "integer" | "decimal" | "boolean" | "date" | "choice";
  is_required: boolean;
  options: Record<string, unknown>;
  display_order: number;
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

export interface TableColumn {
  id: string;
  position: number;
  label: string;
  seed_item_type: string | null;
  seed_item_type_name: string | null;
  seed_container: string | null;
  seed_container_title: string | null;
  relation_type: string | null;
  relation_type_name: string | null;
  relation_forward_label: string | null;
  relation_reverse_label: string | null;
  direction: "outgoing" | "incoming" | null;
}

export interface Table {
  id: string;
  name: string;
  description: string;
  created_by: number;
  created_by_username: string;
  columns: TableColumn[];
  created_at: string;
  updated_at: string;
}

export interface TableColumnPayload {
  position: number;
  label: string;
  seed_item_type?: string | null;
  seed_container?: string | null;
  relation_type?: string | null;
  direction?: "outgoing" | "incoming" | null;
}

export interface TablePayload {
  name: string;
  description?: string;
  columns: TableColumnPayload[];
}

export interface TableDataColumn {
  position: number;
  label: string;
}

export interface TableDataCell {
  id: string;
  title: string;
  item_type_name: string;
  item_type_slug: string;
}

export interface TableData {
  columns: TableDataColumn[];
  rows: (TableDataCell | null)[][];
}

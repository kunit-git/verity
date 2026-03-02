import api from "./client";
import type {
  Item,
  ItemListItem,
  ItemType,
  ItemVersion,
  PaginatedResponse,
  TreeNode,
} from "../types";

export async function getItemTypes() {
  const { data } = await api.get<PaginatedResponse<ItemType>>("/item-types/");
  return data.results;
}

export async function getItemType(id: string) {
  const { data } = await api.get<ItemType>(`/item-types/${id}/`);
  return data;
}

export async function createItemType(payload: {
  name: string;
  slug: string;
  description?: string;
  icon?: string;
}) {
  const { data } = await api.post<ItemType>("/item-types/", payload);
  return data;
}

export async function updateItemType(
  id: string,
  payload: Partial<{ name: string; slug: string; description: string; icon: string }>
) {
  const { data } = await api.patch<ItemType>(`/item-types/${id}/`, payload);
  return data;
}

export async function deleteItemType(id: string) {
  await api.delete(`/item-types/${id}/`);
}

export async function addCustomField(
  itemTypeId: string,
  payload: {
    name: string;
    slug: string;
    field_kind: string;
    is_required?: boolean;
    options?: Record<string, unknown>;
  }
) {
  const { data } = await api.post(
    `/item-types/${itemTypeId}/custom-fields/`,
    payload
  );
  return data;
}

export async function deleteCustomField(itemTypeId: string, fieldId: string) {
  await api.delete(`/item-types/${itemTypeId}/custom-fields/${fieldId}/`);
}

export async function getItems(params?: Record<string, string>) {
  const { data } = await api.get<PaginatedResponse<ItemListItem>>("/items/", {
    params,
  });
  return data;
}

export async function getItem(id: string) {
  const { data } = await api.get<Item>(`/items/${id}/`);
  return data;
}

export async function createItem(payload: {
  title: string;
  description?: string;
  item_type: string;
  status?: string;
  custom_fields?: Record<string, unknown>;
}) {
  const { data } = await api.post<Item>("/items/", payload);
  return data;
}

export async function updateItem(
  id: string,
  payload: Partial<{
    title: string;
    description: string;
    status: string;
    custom_fields: Record<string, unknown>;
  }>
) {
  const { data } = await api.patch<Item>(`/items/${id}/`, payload);
  return data;
}

export async function deleteItem(id: string) {
  await api.delete(`/items/${id}/`);
}

export async function getRootItems(page = 1) {
  const { data } = await api.get<PaginatedResponse<TreeNode>>("/items/roots/", {
    params: { page },
  });
  return data;
}

export async function getItemChildren(id: string, page = 1) {
  const { data } = await api.get<PaginatedResponse<TreeNode>>(
    `/items/${id}/children/`,
    { params: { page } }
  );
  return data;
}

export async function getItemAncestors(id: string) {
  const { data } = await api.get<string[]>(`/items/${id}/ancestors/`);
  return data;
}

export async function reorderChildren(parentId: string, childIds: string[]) {
  const { data } = await api.post(`/items/${parentId}/reorder-children/`, {
    child_ids: childIds,
  });
  return data;
}

export async function getItemVersions(itemId: string) {
  const { data } = await api.get<PaginatedResponse<ItemVersion>>(
    `/items/${itemId}/versions/`
  );
  return data.results;
}

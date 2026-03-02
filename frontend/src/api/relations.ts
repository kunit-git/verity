import api from "./client";
import type {
  ItemRelation,
  NavigationContext,
  PaginatedResponse,
  RelationType,
} from "../types";

export async function getRelationTypes() {
  const { data } =
    await api.get<PaginatedResponse<RelationType>>("/relation-types/");
  return data.results;
}

export async function createRelationType(payload: {
  kind: "composition" | "trace";
  name: string;
  forward_label: string;
  reverse_label: string;
  description?: string;
  source_item_type?: string | null;
  target_item_type?: string | null;
}) {
  const { data } = await api.post<RelationType>("/relation-types/", payload);
  return data;
}

export async function getRelations(params?: Record<string, string>) {
  const { data } = await api.get<PaginatedResponse<ItemRelation>>(
    "/relations/",
    { params }
  );
  return data;
}

export async function createRelation(payload: {
  relation_type: string;
  source: string;
  target: string;
  source_version?: number | null;
  target_version?: number | null;
}) {
  const { data } = await api.post<ItemRelation>("/relations/", payload);
  return data;
}

export async function deleteRelationType(id: string) {
  await api.delete(`/relation-types/${id}/`);
}

export async function deleteRelation(id: string) {
  await api.delete(`/relations/${id}/`);
}

export async function confirmRelation(id: string) {
  const { data } = await api.post<ItemRelation>(`/relations/${id}/confirm/`);
  return data;
}

export async function getNavigation(itemId: string) {
  const { data } = await api.get<NavigationContext>(
    `/items/${itemId}/navigation/`
  );
  return data;
}

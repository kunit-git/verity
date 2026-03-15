import api from "./client";
import type {
  Table,
  TableData,
  TablePayload,
  PaginatedResponse,
} from "../types";

export async function getTables() {
  const { data } = await api.get<PaginatedResponse<Table>>("/tables/");
  return data.results;
}

export async function getTable(id: string) {
  const { data } = await api.get<Table>(`/tables/${id}/`);
  return data;
}

export async function createTable(payload: TablePayload) {
  const { data } = await api.post<Table>("/tables/", payload);
  return data;
}

export async function updateTable(id: string, payload: TablePayload) {
  const { data } = await api.put<Table>(`/tables/${id}/`, payload);
  return data;
}

export async function deleteTable(id: string) {
  await api.delete(`/tables/${id}/`);
}

export async function getTableData(id: string) {
  const { data } = await api.get<TableData>(`/tables/${id}/data/`);
  return data;
}

export async function patchMatrixAnnotation(
  tableId: string,
  columnSlug: string,
  rowHash: string,
  value: string,
): Promise<{ column_slug: string; row_hash: string; value: string }> {
  const { data } = await api.patch(`/tables/${tableId}/annotate/`, {
    column_slug: columnSlug,
    row_hash: rowHash,
    value,
  });
  return data;
}

import api from "./client";
import type { TableData } from "../types";

export async function getItemTableFieldData(
  itemId: string,
  fieldSlug: string,
): Promise<TableData> {
  const { data } = await api.get<TableData>(
    `/items/${itemId}/table-field/${fieldSlug}/data/`,
  );
  return data;
}

export async function patchItemTableAnnotation(
  itemId: string,
  fieldSlug: string,
  columnSlug: string,
  rowHash: string,
  value: string,
): Promise<{ column_slug: string; row_hash: string; value: string }> {
  const { data } = await api.patch(
    `/items/${itemId}/table-field/${fieldSlug}/annotate/`,
    { column_slug: columnSlug, row_hash: rowHash, value },
  );
  return data;
}

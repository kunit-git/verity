import api from "./client";
import type { MailboxArtifact, MailboxArtifactDetail, PaginatedResponse } from "../types";

export async function generateDocument(itemId: string) {
  const { data } = await api.post<MailboxArtifact>("/mailbox/generate/", {
    item_id: itemId,
  });
  return data;
}

export async function getMailboxArtifacts() {
  const { data } = await api.get<PaginatedResponse<MailboxArtifact>>("/mailbox/");
  return data.results;
}

export async function getMailboxArtifact(id: string) {
  const { data } = await api.get<MailboxArtifactDetail>(`/mailbox/${id}/`);
  return data;
}

export async function deleteMailboxArtifact(id: string) {
  await api.delete(`/mailbox/${id}/`);
}

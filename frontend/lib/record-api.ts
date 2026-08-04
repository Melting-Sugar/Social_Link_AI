import { apiClient } from "./api-client";
import type { MessageResponse } from "./auth-api";

export type Condition = "very_good" | "good" | "tired" | "unwell";

export const CONDITION_LABELS: Record<Condition, string> = {
  very_good: "とても良い",
  good: "良い",
  tired: "疲れている",
  unwell: "不調",
};

export interface RecordResponse {
  id: string;
  date: string;
  condition: Condition;
  mood_anxiety_score: number;
  next_goal: string | null;
  memo: string | null;
  summary_bullets: string[];
}

export interface CreateRecordRequest {
  condition: Condition;
  mood_anxiety_score: number;
  next_goal?: string | null;
  memo?: string | null;
  summary_bullets: string[];
}

export const recordApi = {
  log: (conversationId: string, data: CreateRecordRequest) =>
    apiClient.post<RecordResponse>(`/api/conversations/${conversationId}/log`, data),

  list: () => apiClient.get<RecordResponse[]>("/api/records"),

  delete: (recordId: string) => apiClient.delete<MessageResponse>(`/api/records/${recordId}`),
};

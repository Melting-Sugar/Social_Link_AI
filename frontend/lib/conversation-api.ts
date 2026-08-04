import { apiClient } from "./api-client";

export type Scene = "school_university" | "workplace" | "first_meeting" | "friend" | "romantic";

export const SCENE_LABELS: Record<Scene, string> = {
  school_university: "学校・大学",
  workplace: "職場",
  first_meeting: "初対面",
  friend: "友人との会話",
  romantic: "恋愛・気になる人",
};

export type RelationshipDistance = "distant" | "no_change" | "warming_up" | "getting_closer" | "opening_up";

export const RELATIONSHIP_DISTANCE_LABELS: Record<RelationshipDistance, string> = {
  distant: "距離ができている",
  no_change: "変化なし",
  warming_up: "少しずつ打ち解けている",
  getting_closer: "やや近づいている",
  opening_up: "心を開いて話せている",
};

export type SuggestionCategory = "ask_question" | "show_empathy" | "talk_about_self" | "change_topic" | "just_listen";

export const SUGGESTION_CATEGORY_LABELS: Record<SuggestionCategory, string> = {
  ask_question: "質問する",
  show_empathy: "共感を示す",
  talk_about_self: "自分の話をする",
  change_topic: "話題を変える",
  just_listen: "今は聞き役に徹する",
};

export interface ConversationResponse {
  id: string;
  scene: Scene;
  started_at: string;
  ended_at: string | null;
}

export interface RecordingResponse {
  id: string;
  round_number: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message: string | null;
  topic: string | null;
  topic_ready: boolean;
  flow: string | null;
  flow_ready: boolean;
  other_reaction: string | null;
  reaction_ready: boolean;
  relationship_distance: RelationshipDistance | null;
  relationship_ready: boolean;
  suggestion_category: SuggestionCategory | null;
  suggestion_text: string | null;
  suggestion_ready: boolean;
}

export interface SummaryResponse {
  summary_bullets: string[];
}

export const conversationApi = {
  create: (scene: Scene) => apiClient.post<ConversationResponse>("/api/conversations", { scene }),

  get: (conversationId: string) => apiClient.get<ConversationResponse>(`/api/conversations/${conversationId}`),

  uploadRecording: (conversationId: string, audioBlob: Blob, durationSec: number) => {
    const form = new FormData();
    form.append("audio", audioBlob, "recording.webm");
    form.append("duration_sec", String(durationSec));
    return apiClient.postForm<RecordingResponse>(`/api/conversations/${conversationId}/recordings`, form);
  },

  getRecording: (conversationId: string, recordingId: string) =>
    apiClient.get<RecordingResponse>(`/api/conversations/${conversationId}/recordings/${recordingId}`),

  generateSummary: (conversationId: string) =>
    apiClient.post<SummaryResponse>(`/api/conversations/${conversationId}/summary`),
};

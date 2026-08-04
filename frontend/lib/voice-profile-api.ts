import { apiClient } from "./api-client";
import type { MessageResponse } from "./auth-api";

export interface VoiceProfileStatusResponse {
  registered: boolean;
}

export const voiceProfileApi = {
  status: () => apiClient.get<VoiceProfileStatusResponse>("/api/voice-profile"),

  register: (audioBlob: Blob) => {
    const form = new FormData();
    form.append("audio", audioBlob, "voice-enroll.webm");
    return apiClient.postForm<VoiceProfileStatusResponse>("/api/voice-profile", form);
  },

  delete: () => apiClient.delete<MessageResponse>("/api/voice-profile"),
};

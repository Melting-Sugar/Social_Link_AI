import { apiClient } from "./api-client";
import type { Scene } from "./conversation-api";

export interface StatementCheckResponse {
  is_safe: boolean;
  feedback: string;
}

export const statementCheckApi = {
  check: (statementText: string, scene: Scene, relationshipContext?: string) =>
    apiClient.post<StatementCheckResponse>("/api/statement-check", {
      statement_text: statementText,
      scene,
      relationship_context: relationshipContext ?? null,
    }),
};

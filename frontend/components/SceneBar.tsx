import { SCENE_LABELS, type Scene } from "@/lib/conversation-api";

// §11.1: shown persistently at the top of A-③/解析中/A-④ once a scene is
// chosen.
export function SceneBar({ scene }: { scene: Scene }) {
  return (
    <div className="flex items-center gap-2 border-b border-line bg-surface-sunken px-4 py-2.5 text-[12px] text-ink-soft">
      <span className="h-1.5 w-1.5 rounded-full bg-coral" />
      場面：<b className="font-bold text-ink">{SCENE_LABELS[scene]}</b>
    </div>
  );
}

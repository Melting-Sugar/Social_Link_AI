"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { conversationApi, SCENE_LABELS, type Scene } from "@/lib/conversation-api";
import { useAuth } from "@/lib/auth-context";
import { voiceProfileApi } from "@/lib/voice-profile-api";

const SCENES: Scene[] = ["school_university", "workplace", "first_meeting", "friend", "romantic"];
const SCENE_COLORS: Record<Scene, string> = {
  school_university: "bg-scene-1",
  workplace: "bg-scene-2",
  first_meeting: "bg-scene-3",
  friend: "bg-scene-4",
  romantic: "bg-scene-5",
};

export default function ScenePage() {
  const router = useRouter();
  const [isCreating, setIsCreating] = useState(false);
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // proxy.ts can only check for a refresh-token cookie's presence, not
  // validate it (§5) — a stale/expired cookie still lets the request
  // through server-side. This client-side check is the fallback that
  // actually catches that case instead of silently rendering nothing.
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/login?next=/scene");
    }
  }, [authLoading, isAuthenticated, router]);

  // §12.3: 会話サポート開始時に声紋未登録ならE-①へ自動リダイレクト。
  const { data: profileStatus, isLoading } = useQuery({
    queryKey: ["voice-profile-status"],
    queryFn: () => voiceProfileApi.status(),
    enabled: isAuthenticated,
  });

  useEffect(() => {
    if (profileStatus && !profileStatus.registered) {
      router.replace("/voice-enroll?next=/scene");
    }
  }, [profileStatus, router]);

  const handleSelect = async (scene: Scene) => {
    setIsCreating(true);
    try {
      const conversation = await conversationApi.create(scene);
      router.push(`/conversation/${conversation.id}`);
    } finally {
      setIsCreating(false);
    }
  };

  if (isLoading || !profileStatus?.registered) return null;

  return (
    <div className="flex flex-1 flex-col px-5 pb-6 pt-6">
      <h2 className="text-[16px] font-extrabold text-ink">どんな場面ですか？</h2>
      <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">選んだ場面に合わせて、フィードバックの視点を変えます。</p>
      <div className="mt-5 flex flex-col gap-2.5">
        {SCENES.map((scene) => (
          <button
            key={scene}
            type="button"
            disabled={isCreating}
            onClick={() => handleSelect(scene)}
            className={`rounded-2xl px-3.5 py-3.5 text-left text-[13.5px] font-bold text-on-accent transition-[filter] active:brightness-90 disabled:opacity-60 ${SCENE_COLORS[scene]}`}
          >
            {SCENE_LABELS[scene]}
          </button>
        ))}
      </div>
    </div>
  );
}

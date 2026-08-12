"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";
import { voiceProfileApi } from "@/lib/voice-profile-api";

export default function SettingsPage() {
  const router = useRouter();
  const { logout } = useAuth();
  const queryClient = useQueryClient();
  const [isBusy, setIsBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // isBusy(state)だけをガードにすると、Reactの再描画が1回挟まるまでの
  // わずかな間に連打が両方通ってしまう（ボタンのdisabledは再描画後にしか
  // 反映されない）。refは同期的に読み書きできるため、その隙間を塞げる。
  // 3つのハンドラで1つのisBusyを共有しているのに合わせ、refも共有する。
  const isBusyRef = useRef(false);

  const { data: profileStatus } = useQuery({
    queryKey: ["voice-profile-status"],
    queryFn: () => voiceProfileApi.status(),
  });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: () => authApi.me() });

  const handleLogout = async () => {
    if (isBusyRef.current) return;
    isBusyRef.current = true;
    setIsBusy(true);
    await logout();
    router.push("/login");
  };

  const handleDeleteVoiceProfile = async () => {
    if (isBusyRef.current) return;
    isBusyRef.current = true;
    setIsBusy(true);
    try {
      await voiceProfileApi.delete();
      await queryClient.invalidateQueries({ queryKey: ["voice-profile-status"] });
    } finally {
      isBusyRef.current = false;
      setIsBusy(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (isBusyRef.current) return;
    isBusyRef.current = true;
    setIsBusy(true);
    try {
      await authApi.deleteAccount();
      await logout();
      router.push("/login");
    } finally {
      isBusyRef.current = false;
      setIsBusy(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col px-5 py-6">
      <h2 className="text-[16px] font-extrabold text-ink">設定</h2>

      <div className="mt-5 flex flex-col gap-2.5">
        <SettingsRow
          title="声紋の登録"
          subtitle="自分と相手を区別するために使用"
          trailing={
            <span
              className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                profileStatus?.registered ? "bg-coral-tint text-ink" : "bg-caution-tint text-ink"
              }`}
            >
              {profileStatus?.registered ? "登録済み" : "未登録"}
            </span>
          }
          href="/voice-enroll?next=/settings"
        />
        {profileStatus?.registered && (
          <button
            type="button"
            onClick={handleDeleteVoiceProfile}
            disabled={isBusy}
            className="self-start text-[11px] font-bold text-ink-soft underline underline-offset-2"
          >
            声紋データを削除する
          </button>
        )}

        <SettingsRow title="アカウント情報" subtitle={me ? `${me.username} / ${me.email}` : undefined} />
        <SettingsRow title="利用規約" href="/terms" />
        <SettingsRow title="プライバシーポリシー" href="/privacy" />

        <button
          type="button"
          onClick={handleLogout}
          disabled={isBusy}
          className="mt-2 rounded-2xl border border-line bg-surface px-3.5 py-3.5 text-left text-[13px] font-bold text-ink transition-colors active:bg-surface-sunken"
        >
          ログアウト
        </button>
      </div>

      <div className="mt-8 border-t border-line pt-5">
        {!confirmingDelete ? (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className="text-[11.5px] font-bold text-ink underline underline-offset-2"
          >
            アカウントを削除する
          </button>
        ) : (
          <div className="rounded-2xl border border-line bg-caution-tint p-4">
            <p className="text-[12.5px] leading-relaxed text-ink">
              アカウントを削除すると、声紋・会話の記録などすべてのデータが削除され、元に戻せません。本当に削除しますか？
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="flex-1 rounded-2xl border border-line bg-surface px-3.5 py-2.5 text-[12.5px] font-bold text-ink transition-colors active:bg-surface-sunken"
              >
                キャンセル
              </button>
              <PrimaryButton
                onClick={handleDeleteAccount}
                disabled={isBusy}
                className="flex-1 !bg-caution active:!bg-caution-strong"
              >
                削除する
              </PrimaryButton>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SettingsRow({
  title,
  subtitle,
  trailing,
  href,
}: {
  title: string;
  subtitle?: string;
  trailing?: React.ReactNode;
  href?: string;
}) {
  const content = (
    <div className="flex items-center justify-between gap-2 rounded-2xl border border-line bg-surface px-3.5 py-3.5">
      <div className="flex flex-col gap-0.5">
        <span className="text-[13px] font-bold text-ink">{title}</span>
        {subtitle && <span className="text-[10.5px] text-ink-soft">{subtitle}</span>}
      </div>
      {trailing}
    </div>
  );
  if (!href) return content;
  return (
    <Link href={href} className="block">
      {content}
    </Link>
  );
}

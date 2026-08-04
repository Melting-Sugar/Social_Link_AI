"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AuthPageShell } from "@/components/ui/AuthPageShell";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { TextField } from "@/components/ui/TextField";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { passwordSchema } from "@/lib/validation";

const schema = z
  .object({
    new_password: passwordSchema,
    new_password_confirm: z.string(),
  })
  .refine((data) => data.new_password === data.new_password_confirm, {
    message: "パスワードが一致しません。",
    path: ["new_password_confirm"],
  });
type FormValues = z.infer<typeof schema>;

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await authApi.resetPassword({ token, ...values });
      setDone(true);
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "パスワードの再設定に失敗しました。");
    }
  };

  if (!token) {
    return <p className="text-[13px] leading-relaxed text-ink">リンクが正しくありません。メールに記載のリンクからアクセスしてください。</p>;
  }

  if (done) {
    return <p className="text-[13px] leading-relaxed text-ink">パスワードを再設定しました。ログイン画面に移動します…</p>;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <TextField
        label="新しいパスワード"
        type="password"
        autoComplete="new-password"
        hint="8文字以上、半角英字・全角英字・数字・記号のうち2種類以上を組み合わせてください。"
        error={errors.new_password?.message}
        {...register("new_password")}
      />
      <TextField
        label="新しいパスワード（確認）"
        type="password"
        autoComplete="new-password"
        error={errors.new_password_confirm?.message}
        {...register("new_password_confirm")}
      />
      {formError && <p className="text-[12px] text-ink">{formError}</p>}
      <PrimaryButton disabled={isSubmitting}>{isSubmitting ? "設定中..." : "パスワードを再設定する"}</PrimaryButton>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthPageShell title="パスワード再設定">
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </AuthPageShell>
  );
}

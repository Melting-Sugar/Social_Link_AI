"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AuthPageShell } from "@/components/ui/AuthPageShell";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { TextField } from "@/components/ui/TextField";
import { TextLink } from "@/components/ui/TextLink";
import { authApi } from "@/lib/auth-api";
import { emailSchema } from "@/lib/validation";

const schema = z.object({ email: emailSchema });
type FormValues = z.infer<typeof schema>;

export default function ForgotUsernamePage() {
  const [message, setMessage] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    // §11.2: response is identical whether or not the account exists —
    // never surface a request-level error here either.
    const result = await authApi.forgotUsername(values.email);
    setMessage(result.message);
  };

  return (
    <AuthPageShell title="ユーザー名を忘れた場合" description="登録済みのメールアドレスを入力してください。">
      {message ? (
        <p className="text-[13px] leading-relaxed text-ink">{message}</p>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          <TextField
            label="メールアドレス"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register("email")}
          />
          <PrimaryButton disabled={isSubmitting}>{isSubmitting ? "送信中..." : "送信する"}</PrimaryButton>
        </form>
      )}
      <div className="border-t border-line pt-4 text-center">
        <TextLink href="/login">ログイン画面に戻る</TextLink>
      </div>
    </AuthPageShell>
  );
}

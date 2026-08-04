"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AuthPageShell } from "@/components/ui/AuthPageShell";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { TextField } from "@/components/ui/TextField";
import { TextLink } from "@/components/ui/TextLink";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";
import { emailSchema, passwordSchema, usernameSchema } from "@/lib/validation";

const schema = z
  .object({
    email: emailSchema,
    username: usernameSchema,
    password: passwordSchema,
    password_confirm: z.string(),
  })
  .refine((data) => data.password === data.password_confirm, {
    message: "パスワードが一致しません。",
    path: ["password_confirm"],
  });
type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      const { access_token } = await authApi.register(values);
      login(access_token);
      router.push("/");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "登録に失敗しました。");
    }
  };

  return (
    <AuthPageShell title="はじめまして" description="すぐに始められます。">
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
        <TextField
          label="メールアドレス"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <TextField
          label="ユーザー名"
          autoComplete="username"
          error={errors.username?.message}
          {...register("username")}
        />
        <TextField
          label="パスワード"
          type="password"
          autoComplete="new-password"
          hint="8文字以上、半角英字・全角英字・数字・記号のうち2種類以上を組み合わせてください。"
          error={errors.password?.message}
          {...register("password")}
        />
        <TextField
          label="パスワード（確認）"
          type="password"
          autoComplete="new-password"
          error={errors.password_confirm?.message}
          {...register("password_confirm")}
        />
        {formError && <p className="text-[12px] text-ink">{formError}</p>}
        <PrimaryButton disabled={isSubmitting}>{isSubmitting ? "登録中..." : "登録する"}</PrimaryButton>
      </form>
      <div className="flex flex-col gap-2 border-t border-line pt-4 text-center">
        <TextLink href="/login">既にアカウントをお持ちの方はこちら</TextLink>
      </div>
    </AuthPageShell>
  );
}

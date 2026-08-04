"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AuthPageShell } from "@/components/ui/AuthPageShell";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { TextField } from "@/components/ui/TextField";
import { TextLink } from "@/components/ui/TextLink";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";

const schema = z.object({
  identifier: z.string().min(1, "メールアドレスまたはユーザー名を入力してください。"),
  password: z.string().min(1, "パスワードを入力してください。"),
});
type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      const { access_token } = await authApi.login(values);
      login(access_token);
      router.push(searchParams.get("next") ?? "/");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "ログインに失敗しました。");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <TextField
        label="メールアドレス または ユーザー名"
        autoComplete="username"
        error={errors.identifier?.message}
        {...register("identifier")}
      />
      <TextField
        label="パスワード"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        {...register("password")}
      />
      {formError && <p className="text-[12px] text-ink">{formError}</p>}
      <PrimaryButton disabled={isSubmitting}>{isSubmitting ? "ログイン中..." : "ログイン"}</PrimaryButton>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthPageShell title="おかえりなさい" description="メールアドレスまたはユーザー名でログインしてください。">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
      <div className="flex flex-col gap-2 border-t border-line pt-4 text-center">
        <TextLink href="/forgot-username">ユーザー名を忘れた場合</TextLink>
        <TextLink href="/forgot-password">パスワードを忘れた場合</TextLink>
        <TextLink href="/register">アカウントをお持ちでない方はこちら</TextLink>
      </div>
    </AuthPageShell>
  );
}

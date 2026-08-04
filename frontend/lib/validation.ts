import { z } from "zod";

// Mirrors backend/app/core/security.py's validate_password_strength (§11.2)
// — instant client-side feedback, but the backend re-validates regardless
// (never trust client-side validation alone).
const HALFWIDTH_ALPHA = /[A-Za-z]/;
const FULLWIDTH_ALPHA = /[Ａ-Ｚａ-ｚ]/;
const DIGIT = /[0-9０-９]/;
const SYMBOL = /[!-/:-@[-`{-~　-〿！-／：-＠［-｀｛-･]/;

export function passwordClassCount(password: string): number {
  return [HALFWIDTH_ALPHA, FULLWIDTH_ALPHA, DIGIT, SYMBOL].filter((re) => re.test(password)).length;
}

export const passwordSchema = z
  .string()
  .min(8, "パスワードは8文字以上で入力してください。")
  .refine(
    (v) => passwordClassCount(v) >= 2,
    "パスワードは、半角英字・全角英字・数字・記号のうち2種類以上を組み合わせてください。"
  );

export const usernameSchema = z
  .string()
  .min(3, "ユーザー名は3〜64文字で入力してください。")
  .max(64, "ユーザー名は3〜64文字で入力してください。");

export const emailSchema = z.string().email("メールアドレスの形式が正しくありません。");

// Small pieces every screen uses.
import type { ReactNode } from "react";
import { ApiError } from "./api.js";
import { Label } from "@/components/ui/label";

export type User = { id: string; email: string; name: string; mustChange: boolean; isAdmin: boolean };

const MESSAGES: Record<string, string> = {
  wrong_email_or_password: "Wrong email or password.",
  too_many_attempts: "Too many tries. Wait fifteen minutes.",
  wrong_password: "That is not your current password.",
  password_too_short: "Use at least 10 characters.",
  password_unchanged: "Choose a different password.",
  email_taken_or_invalid: "That email is already in use, or is not an email address.",
  no_account: "There is no __App__ account for that address.",
  sign_in_failed: "That sign-in did not finish. Try again.",
};
export const say = (error: unknown) => (error instanceof ApiError ? (MESSAGES[error.code] ?? error.message) : "Could not reach the server.");
export const sayCode = (code: string) => MESSAGES[code] ?? MESSAGES["sign_in_failed"]!;

export const Field = ({ label, children }: { label: string; children: ReactNode }) => <Label className="grid gap-1.5 text-muted-foreground">{label}{children}</Label>;
export const Problem = ({ children }: { children: string | null }) => (children ? <p className="text-sm text-destructive" role="alert">{children}</p> : null);

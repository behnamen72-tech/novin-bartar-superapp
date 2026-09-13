"use client";

import type { FormEvent } from "react";
import { AppNotice } from "@/components/ui/AppNotice";

type LoginScreenProps = {
  login: string;
  password: string;
  submitting: boolean;
  message: string;
  onLoginChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function LoginScreen({
  login,
  password,
  submitting,
  message,
  onLoginChange,
  onPasswordChange,
  onSubmit,
}: LoginScreenProps) {
  return (
    <main className="login-shell">
      <section className="login-intro">
        <div className="eyebrow">NOVIN BARTAR • SUPER APP</div>
        <h1>مرکز مدیریت انفرادی مارکت</h1>
        <p>
          رابط مدیریتی یکپارچه برای سازمان، اشخاص، کاربران، دسترسی‌ها و اسناد؛
          متصل به Core امن نوین برتر.
        </p>
        <div className="login-feature-grid">
          <div>
            <strong>نشست امن</strong>
            <span>Access Token کوتاه‌عمر + Refresh Token چرخشی</span>
          </div>
          <div>
            <strong>Core عملیاتی</strong>
            <span>مدیریت سازمان، اشخاص، کاربران و دسترسی‌ها</span>
          </div>
          <div>
            <strong>دسترسی سازمانی</strong>
            <span>Role + Permission + Organization Scope</span>
          </div>
        </div>
      </section>

      <section className="login-card" aria-labelledby="login-title">
        <div className="brand-row">
          <div className="brand-mark">NB</div>
          <div>
            <strong>نوین برتر</strong>
            <span>سوپر اپ انفرادی مارکت</span>
          </div>
        </div>

        <div className="login-heading">
          <span id="login-title">ورود به محیط مدیریت</span>
          <p>با حساب کاربری خود وارد شوید. اطلاعات ورود در مرورگر ذخیره نمی‌شود.</p>
        </div>

        <form onSubmit={onSubmit}>
          <label>
            ایمیل یا نام کاربری
            <input
              value={login}
              onChange={(event) => onLoginChange(event.target.value)}
              autoComplete="username"
              autoFocus
              required
              maxLength={320}
              dir="ltr"
            />
          </label>

          <label>
            رمز عبور
            <input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              autoComplete="current-password"
              required
              maxLength={1024}
              dir="ltr"
            />
          </label>

          {message ? <AppNotice tone="error">{message}</AppNotice> : null}

          <button type="submit" disabled={submitting}>
            {submitting ? "در حال ورود…" : "ورود به سوپر اپ"}
          </button>
        </form>

        <div className="demo-hint">
          <span>B6.4 • Operational Dashboard</span>
          <small>نشست امن، ناوبری دسترسی‌محور و داشبورد زنده Core</small>
        </div>
      </section>
    </main>
  );
}

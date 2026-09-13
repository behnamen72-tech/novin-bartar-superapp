"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Frontend route error", error);
  }, [error]);

  return (
    <main className="system-state-screen">
      <div className="system-state-card">
        <div className="brand-mark">NB</div>
        <h1>خطایی در رابط کاربری رخ داد</h1>
        <p>اطلاعات شما تغییر نکرده است. می‌توانید این بخش را دوباره بارگذاری کنید.</p>
        <button type="button" onClick={reset}>تلاش دوباره</button>
      </div>
    </main>
  );
}

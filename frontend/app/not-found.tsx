import Link from "next/link";

export default function NotFound() {
  return (
    <main className="system-state-screen">
      <div className="system-state-card">
        <div className="brand-mark">NB</div>
        <h1>صفحه پیدا نشد</h1>
        <p>آدرس واردشده در این نسخه از سوپر اپ وجود ندارد.</p>
        <Link href="/">بازگشت به داشبورد</Link>
      </div>
    </main>
  );
}

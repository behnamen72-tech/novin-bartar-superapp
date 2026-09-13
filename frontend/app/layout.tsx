import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "سوپر اپ نوین برتر",
  description: "پلتفرم مدیریت یکپارچه نوین برتر",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body>{children}</body>
    </html>
  );
}

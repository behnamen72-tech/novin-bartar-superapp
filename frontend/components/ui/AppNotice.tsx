export type AppNoticeTone = "info" | "error" | "success";

export function AppNotice({
  children,
  tone = "info",
}: {
  children: React.ReactNode;
  tone?: AppNoticeTone;
}) {
  return (
    <div className={`app-notice app-notice-${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

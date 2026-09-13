export function AsyncState({ label = "در حال دریافت اطلاعات…" }: { label?: string }) {
  return (
    <div className="async-state" role="status" aria-live="polite">
      <span className="async-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

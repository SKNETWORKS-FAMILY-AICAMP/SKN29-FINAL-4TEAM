import "./EmptyState.css";

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({
  title = "표시할 정보가 없습니다.",
  description = "조건을 변경한 뒤 다시 확인해 주세요.",
  actionLabel,
  onAction,
}: EmptyStateProps) {
  const shouldShowAction = Boolean(actionLabel && onAction);

  return (
    <section
      className="empty-state"
      role="status"
      aria-live="polite"
    >
      <div className="empty-state__icon" aria-hidden="true">
        ⓘ
      </div>

      <strong className="empty-state__title">{title}</strong>

      <p className="empty-state__description">{description}</p>

      {shouldShowAction && (
        <button
          type="button"
          className="empty-state__action"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </section>
  );
}

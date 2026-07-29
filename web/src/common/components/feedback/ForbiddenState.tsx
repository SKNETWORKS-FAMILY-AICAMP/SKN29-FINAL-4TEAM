import "./ForbiddenState.css";

interface ForbiddenStateProps {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function ForbiddenState({
  title = "접근 권한이 없습니다.",
  description = "이 화면을 볼 수 있는 권한이 있는지 확인해 주세요.",
  actionLabel,
  onAction,
}: ForbiddenStateProps) {
  return (
    <section
      className="forbidden-state"
      role="alert"
      aria-live="assertive"
    >
      <div className="forbidden-state__icon" aria-hidden="true">
        🔒
      </div>

      <strong className="forbidden-state__title">{title}</strong>

      <p className="forbidden-state__description">{description}</p>

      {actionLabel && onAction && (
        <button
          type="button"
          className="forbidden-state__action"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </section>
  );
}
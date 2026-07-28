import "./ErrorState.css";

interface ErrorStateProps {
  title?: string;
  description?: string;
  retryLabel?: string;
  onRetry?: () => void;
}

export default function ErrorState({
  title = "정보를 불러오지 못했습니다.",
  description = "잠시 후 다시 시도해 주세요.",
  retryLabel = "다시 시도",
  onRetry,
}: ErrorStateProps) {
  return (
    <section
      className="error-state"
      role="alert"
      aria-live="assertive"
    >
      <div className="error-state__icon" aria-hidden="true">
        !
      </div>

      <strong className="error-state__title">{title}</strong>

      <p className="error-state__description">{description}</p>

      {onRetry && (
        <button
          type="button"
          className="error-state__retry-button"
          onClick={onRetry}
        >
          {retryLabel}
        </button>
      )}
    </section>
  );
}
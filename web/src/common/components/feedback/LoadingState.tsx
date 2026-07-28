import "./LoadingState.css";

interface LoadingStateProps {
  title?: string;
  description?: string;
}

export default function LoadingState({
  title = "정보를 불러오고 있습니다.",
  description = "잠시만 기다려 주세요.",
}: LoadingStateProps) {
  return (
    <section
      className="loading-state"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="loading-state__spinner" aria-hidden="true" />

      <strong className="loading-state__title">{title}</strong>

      <p className="loading-state__description">{description}</p>
    </section>
  );
}

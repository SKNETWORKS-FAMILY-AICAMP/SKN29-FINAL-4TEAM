interface InquirySectionErrorProps {
  title: string;
  description: string;
}

export default function InquirySectionError({
  title,
  description,
}: InquirySectionErrorProps) {
  return (
    <div
      className="inquiry-detail__section-error"
      role="alert"
      aria-live="polite"
    >
      <span aria-hidden="true">!</span>

      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}

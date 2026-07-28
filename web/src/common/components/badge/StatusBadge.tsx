import "./StatusBadge.css";

export type StatusBadgeVariant =
  | "default"
  | "progress"
  | "reopened"
  | "success"
  | "danger";

interface StatusBadgeProps {
  label: string;
  size?: "default" | "compact";
  variant?: StatusBadgeVariant;
}

export default function StatusBadge({
  label,
  size = "default",
  variant = "default",
}: StatusBadgeProps) {
  return (
    <span
      className={`common-status-badge common-status-badge--${variant} common-status-badge--${size}`}
      aria-label={`상태: ${label}`}
    >
      {label}
    </span>
  );
}

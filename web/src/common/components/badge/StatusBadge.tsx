import "./StatusBadge.css";

interface StatusBadgeProps {
  label: string;
  variant?: "default" | "progress" | "reopened";
}

export default function StatusBadge({
  label,
  variant = "default",
}: StatusBadgeProps) {
  return (
    <span
      className={`common-status-badge common-status-badge--${variant}`}
    >
      {label}
    </span>
  );
}

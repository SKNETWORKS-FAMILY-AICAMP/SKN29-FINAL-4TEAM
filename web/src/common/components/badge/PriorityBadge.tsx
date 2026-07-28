import "./PriorityBadge.css";

export type PriorityBadgeVariant = "default" | "high" | "urgent";

interface PriorityBadgeProps {
  label?: string | null;
  variant?: PriorityBadgeVariant;
}

const PRIORITY_ICONS: Record<PriorityBadgeVariant, string> = {
  default: "●",
  high: "▲",
  urgent: "!",
};

export default function PriorityBadge({
  label,
  variant = "default",
}: PriorityBadgeProps) {
  const displayLabel = label?.trim() || "미확인";

  return (
    <span
      className={`common-priority-badge common-priority-badge--${variant}`}
      aria-label={`우선순위: ${displayLabel}`}
    >
      <span className="common-priority-badge__icon" aria-hidden="true">
        {PRIORITY_ICONS[variant]}
      </span>
      {displayLabel}
    </span>
  );
}

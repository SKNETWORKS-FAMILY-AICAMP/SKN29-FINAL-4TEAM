import "./RiskBadge.css";

export type RiskLevel = "general" | "caution" | "danger";

interface RiskPresentation {
  icon: string;
  label: string;
  level: RiskLevel | "unknown";
}

const RISK_PRESENTATIONS: Record<RiskLevel, RiskPresentation> = {
  general: { icon: "●", label: "일반", level: "general" },
  caution: { icon: "▲", label: "주의", level: "caution" },
  danger: { icon: "!", label: "위험", level: "danger" },
};

const UNKNOWN_RISK: RiskPresentation = {
  icon: "?",
  label: "미확인",
  level: "unknown",
};

interface RiskBadgeProps {
  level?: string | null;
}

function isRiskLevel(value: string): value is RiskLevel {
  return value in RISK_PRESENTATIONS;
}

export default function RiskBadge({ level }: RiskBadgeProps) {
  const presentation =
    level && isRiskLevel(level)
      ? RISK_PRESENTATIONS[level]
      : UNKNOWN_RISK;

  return (
    <span
      className={`common-risk-badge common-risk-badge--${presentation.level}`}
      aria-label={`위험도: ${presentation.label}`}
    >
      <span className="common-risk-badge__icon" aria-hidden="true">
        {presentation.icon}
      </span>
      {presentation.label}
    </span>
  );
}

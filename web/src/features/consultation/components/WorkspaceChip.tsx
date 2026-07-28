interface WorkspaceChipProps {
  label: string;
  tone?: string;
}

export default function WorkspaceChip({
  label,
  tone = "outline",
}: WorkspaceChipProps) {
  return <span className={`v6-chip v6-chip--${tone}`}>{label}</span>;
}

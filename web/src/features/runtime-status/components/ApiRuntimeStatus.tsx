import useApiRuntimeStatus from "../hooks/useApiRuntimeStatus";
import { appEnv } from "../../../app/config/env";
import "./ApiRuntimeStatus.css";

type ApiRuntimeStatusProps = {
  className?: string;
  compact?: boolean;
};

const STATUS_LABELS = {
  checking: "API 확인 중",
  connected: "API 서버 연결됨",
  unavailable: "API 서버 연결 대기",
} as const;

export default function ApiRuntimeStatus({
  className = "",
  compact = false,
}: ApiRuntimeStatusProps) {
  const runtime = useApiRuntimeStatus();
  const dataSourceLabel = appEnv.useMockApi ? "Mock" : "Backend API";
  const checkedTime =
    runtime.status === "connected"
      ? new Intl.DateTimeFormat("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }).format(new Date(runtime.probe.checkedAt))
      : null;

  return (
    <div
      className={`api-runtime-status api-runtime-status--${runtime.status}${
        compact ? " api-runtime-status--compact" : ""
      } ${className}`.trim()}
      aria-live="polite"
      title={
        runtime.status === "connected"
          ? `마지막 확인 ${checkedTime} · ${runtime.probe.latencyMs}ms · 화면 업무 데이터는 ${dataSourceLabel}`
          : `백엔드 /health 응답을 기다리고 있습니다. 화면 업무 데이터는 ${dataSourceLabel}입니다.`
      }
    >
      <span className="api-runtime-status__signal" aria-hidden="true" />
      <span>
        <strong>{STATUS_LABELS[runtime.status]}</strong>
        {!compact && <small>화면 업무 데이터 {dataSourceLabel}</small>}
      </span>
    </div>
  );
}

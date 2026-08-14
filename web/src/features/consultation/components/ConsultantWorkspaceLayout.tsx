import { useAuth } from "../../../app/providers/authContext";
import type { ReactNode } from "react";
import { appEnv } from "../../../app/config/env";

interface ConsultantWorkspaceLayoutProps {
  activeSection?: "queue" | "detail" | "visit";
  children: ReactNode;
  notificationOpen: boolean;
  queueCount: number;
  onCloseNotifications: () => void;
  onNavigate: (target: "queue" | "detail" | "visit") => void;
  onToggleNotifications: () => void;
}

export default function ConsultantWorkspaceLayout({
  activeSection = "queue",
  children,
  notificationOpen,
  queueCount,
  onCloseNotifications,
  onNavigate,
  onToggleNotifications,
}: ConsultantWorkspaceLayoutProps) {
  const { user } = useAuth();

  const displayName = user?.displayName ?? "상담사";
  const avatarText = displayName.trim().charAt(0) || "상";
  const roleLabel = user?.roleCode === "CONSULTANT" ? "상담원" : "사용자";

  const workspaceSource = appEnv.useMockApi ? "합성 Mock 화면" : "Backend API 연결 화면";
  return (
    <div className="v6-workspace">
      <a className="v6-skip-link" href="#v6-main">
        본문 바로가기
      </a>

      <header className="v6-topbar">
        <a
          className="v6-brand"
          href="/"
          aria-label="Water Bridge 역할 선택 홈으로 이동"
        >
          <span className="v6-brand__mark" aria-hidden="true">
            W
          </span>
          <span>
            <strong>Water Bridge</strong>
            <small>상담원 워크스페이스</small>
          </span>
        </a>

        <div className="v6-topbar__context" aria-label="현재 업무 컨텍스트">
          <span className="v6-live-dot">
            <i /> {workspaceSource}
          </span>
          <span>
            기준 모델 <b>WPUJAC104DWH</b>
          </span>
          <span>화면설계 v13</span>
        </div>

        <div className="v6-topbar__actions">
          <button
            className="v6-icon-button"
            type="button"
            aria-label="상담원 알림, 읽지 않은 알림 1개"
            aria-expanded={notificationOpen}
            onClick={onToggleNotifications}
          >
            <span aria-hidden="true">●</span>
            <b>1</b>
          </button>

          <div className="v6-user-chip">
            <span>{avatarText}</span>
            <div>
              <strong>{displayName}</strong>
              <small>{roleLabel}</small>
            </div>
          </div>
        </div>
      </header>

      <div className="v6-shell">
        <aside className="v6-sidebar" aria-label="상담원 화면 메뉴">
          <div className="v6-sidebar__section">
            <p>COUNSELOR</p>
            <button
              className={`v6-nav-item ${activeSection === "queue" ? "is-active" : ""}`}
              type="button"
              aria-current={activeSection === "queue" ? "page" : undefined}
              onClick={() => onNavigate("queue")}
            >
              <span aria-hidden="true">◎</span>
              <span>상담 큐</span>
              <b>{queueCount}</b>
            </button>
            <button
              className={`v6-nav-item ${activeSection === "detail" ? "is-active" : ""}`}
              type="button"
              aria-current={activeSection === "detail" ? "page" : undefined}
              onClick={() => onNavigate("detail")}
            >
              <span aria-hidden="true">▤</span>
              <span>문의 상세</span>
            </button>
            <button
              className={`v6-nav-item ${activeSection === "visit" ? "is-active" : ""}`}
              type="button"
              aria-current={activeSection === "visit" ? "page" : undefined}
              onClick={() => onNavigate("visit")}
            >
              <span aria-hidden="true">□</span>
              <span>방문 전환</span>
            </button>
          </div>

          <div className="v6-sidebar__legend">
            <p>처리 원칙</p>
            <ul>
              <li>
                <i className="is-danger" />위험·상담 필수 우선
              </li>
              <li>
                <i className="is-warning" />고객 최종확인 대기
              </li>
              <li>
                <i className="is-safe" />공식 근거 확인
              </li>
            </ul>
          </div>

          <a className="v6-home-link" href="/">
            <span aria-hidden="true">←</span> 역할 선택 홈
          </a>
        </aside>

        <main id="v6-main" className="v6-main" tabIndex={-1}>
          {children}
        </main>
      </div>

      {!notificationOpen ? null : (
        <section
          className="v6-notification-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="counselor-notification-title"
        >
          <header>
            <div>
              <small>WORK NOTIFICATIONS</small>
              <h2 id="counselor-notification-title">상담 업무 알림</h2>
            </div>
            <button
              type="button"
              aria-label="알림 닫기"
              onClick={onCloseNotifications}
            >
              ×
            </button>
          </header>

          <div className="v6-notification-list">
            <button
              type="button"
              className="v6-notification-item is-unread is-danger"
              onClick={() => {
                onNavigate("detail");
                onCloseNotifications();
              }}
            >
              <span>!</span>
              <div>
                <strong>고객 해결 피드백 도착</strong>
                <p>INQ-20260705-0017 문의를 최종 확인해 주세요.</p>
                <small>합성 시연 · 방금 전</small>
              </div>
            </button>
          </div>
          <footer>알림을 선택하면 연결된 문의 상세를 엽니다.</footer>
        </section>
      )}
    </div>
  );
}

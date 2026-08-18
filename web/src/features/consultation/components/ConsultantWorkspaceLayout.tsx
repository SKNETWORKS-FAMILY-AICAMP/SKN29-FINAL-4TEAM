import type { ReactNode } from "react";
import ConsultantUserMenu from "./ConsultantUserMenu";

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
}: ConsultantWorkspaceLayoutProps) {
  return (
    <div className="v6-workspace">
      <a className="v6-skip-link" href="#v6-main">
        본문 바로가기
      </a>

      <header className="v6-topbar consultant-unified-header">
        <ConsultantUserMenu />
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

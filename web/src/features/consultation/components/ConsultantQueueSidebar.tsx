import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link, useNavigate } from "react-router-dom";

import { ROUTE_PATHS } from "../../../app/router/routePaths";
import { WORK_BUCKET_LABELS } from "../model/consultantWorkspaceModel";
import type { CounselorWorkBucket } from "../model/consultantWorkspaceTypes";
import "./ConsultantQueueSidebar.css";

export type ConsultantInquiryBucket = CounselorWorkBucket | "ALL";

const WORK_BUCKETS: readonly ConsultantInquiryBucket[] = [
  "ALL",
  "IN_PROGRESS",
  "COMPLETED",
];

let isSidebarExpanded = false;

function WorkBucketIcon({ bucket }: { bucket: ConsultantInquiryBucket }) {
  if (bucket === "ALL") {
    return (
      <svg
        className="consultant-work-tab__icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path d="M5 5.5h14v4H5zM5 12h14v6.5H5z" />
      </svg>
    );
  }

  if (bucket === "NEW") {
    return (
      <svg
        className="consultant-work-tab__icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path d="M4 6.5h16v11H4z" />
        <path d="m4.8 7.3 7.2 5.4 7.2-5.4" />
      </svg>
    );
  }

  if (bucket === "IN_PROGRESS") {
    return (
      <svg
        className="consultant-work-tab__icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v4.8l3.2 2" />
      </svg>
    );
  }

  return (
    <svg
      className="consultant-work-tab__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="8" />
      <path d="m8.6 12.2 2.2 2.3 4.8-5" />
    </svg>
  );
}

function PhoneInquiryIcon() {
  return (
    <svg
      className="consultant-work-tab__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M7.2 4.5 9.7 8 8.2 9.7a13.2 13.2 0 0 0 6.1 6.1l1.7-1.5 3.5 2.5-.8 2.7c-.3.8-1.1 1.3-2 1.2C9.8 20 4 14.2 3.3 7.3c-.1-.9.4-1.7 1.2-2z" />
      <path d="M14.5 5.5h5M17 3v5" />
    </svg>
  );
}

function DashboardIcon() {
  return (
    <svg
      className="consultant-work-tab__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="4.5" rx="1.5" />
      <rect x="13.5" y="10.5" width="7" height="10" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function NoticeIcon() {
  return (
    <svg
      className="consultant-work-tab__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M6 4.5h12v15H6z" />
      <path d="M9 8h6M9 11.5h6M9 15h4" />
    </svg>
  );
}

function ContactsIcon() {
  return (
    <svg
      className="consultant-work-tab__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="5" y="3.5" width="15" height="17" rx="2" />
      <path d="M3 7h4M3 12h4M3 17h4" />
      <circle cx="12.5" cy="9" r="2" />
      <path d="M9 16v-1a3.5 3.5 0 0 1 7 0v1" />
    </svg>
  );
}

interface ConsultantQueueSidebarProps {
  activeBucket: ConsultantInquiryBucket | null;
  bucketCounts?: Readonly<Record<CounselorWorkBucket, number>>;
  totalCount?: number;
  dashboardActive?: boolean;
  noticeActive?: boolean;
  contactsActive?: boolean;
  phoneEntryActive?: boolean;
  onBucketChange?: (bucket: ConsultantInquiryBucket) => void;
}

export default function ConsultantQueueSidebar({
  activeBucket,
  bucketCounts,
  totalCount,
  dashboardActive = false,
  noticeActive = false,
  contactsActive = false,
  phoneEntryActive = false,
  onBucketChange,
}: ConsultantQueueSidebarProps) {
  const navigate = useNavigate();
  const sidebarRef = useRef<HTMLElement>(null);
  const [isExpanded, setIsExpanded] = useState(() => isSidebarExpanded);

  const updateExpandedState = useCallback((expanded: boolean) => {
    isSidebarExpanded = expanded;
    setIsExpanded(expanded);
  }, []);

  useEffect(() => {
    if (!isExpanded) return;

    const collapseWithEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      updateExpandedState(false);
      sidebarRef.current
        ?.querySelector<HTMLButtonElement>(".consultant-sidebar-toggle")
        ?.focus();
    };

    document.addEventListener("keydown", collapseWithEscape);

    return () => {
      document.removeEventListener("keydown", collapseWithEscape);
    };
  }, [isExpanded, updateExpandedState]);

  const openBucket = (bucket: ConsultantInquiryBucket) => {
    if (onBucketChange) {
      onBucketChange(bucket);
      return;
    }
    navigate(`${ROUTE_PATHS.consultantInquiryList}?bucket=${bucket}`);
  };

  return (
    <aside
      ref={sidebarRef}
      id="consultant-queue-sidebar"
      className={`consultant-sidebar${
        isExpanded ? " is-user-expanded" : ""
      }`}
      aria-label="상담사 사이드바"
    >
      <button
        type="button"
        className="consultant-sidebar-toggle"
        aria-controls="consultant-sidebar-navigation"
        aria-expanded={isExpanded}
        aria-label={isExpanded ? "사이드바 축소" : "사이드바 펼치기"}
        onClick={() => updateExpandedState(!isExpanded)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          {isExpanded ? (
            <path d="m14.5 6-6 6 6 6" />
          ) : (
            <path d="m9.5 6 6 6-6 6" />
          )}
        </svg>
      </button>
      <nav
        id="consultant-sidebar-navigation"
        className="consultant-work-tabs"
        aria-label="상담사 메뉴"
        role="tablist"
      >
        <Link
          to={ROUTE_PATHS.consultantDashboard}
          role="tab"
          aria-selected={dashboardActive}
          aria-controls="consultant-dashboard-panel"
          className={`consultant-work-tab consultant-work-tab--dashboard${
            dashboardActive ? " is-active" : ""
          }`}
        >
          <span>
            <DashboardIcon />
            <strong>업무 대시보드</strong>
          </span>
        </Link>

        {WORK_BUCKETS.map((bucket) => (
          <button
            key={bucket}
            type="button"
            role="tab"
            aria-selected={
              !dashboardActive &&
              !noticeActive &&
              !contactsActive &&
              !phoneEntryActive &&
              activeBucket === bucket
            }
            aria-controls="consultant-queue-panel"
            className={`consultant-work-tab consultant-work-tab--${bucket.toLowerCase()}${
              !dashboardActive &&
              !noticeActive &&
              !contactsActive &&
              !phoneEntryActive &&
              activeBucket === bucket
                ? " is-active"
                : ""
            }`}
            onClick={() => openBucket(bucket)}
          >
            <span>
              <WorkBucketIcon bucket={bucket} />
              <strong>{bucket === "ALL" ? "전체 문의" : WORK_BUCKET_LABELS[bucket]}</strong>
            </span>
            {bucketCounts && (
              <b>
                {bucket === "ALL"
                  ? totalCount ??
                    (bucketCounts.NEW +
                      bucketCounts.IN_PROGRESS +
                      bucketCounts.COMPLETED)
                  : bucketCounts[bucket]}
              </b>
            )}
          </button>
        ))}

        <Link
          to={ROUTE_PATHS.consultantPhoneInquiryCreate}
          role="tab"
          aria-selected={!dashboardActive && phoneEntryActive}
          aria-controls="consultant-phone-entry-panel"
          className={`consultant-work-tab consultant-work-tab--phone${
            !dashboardActive && phoneEntryActive ? " is-active" : ""
          }`}
        >
          <span>
            <PhoneInquiryIcon />
            <strong>전화 문의 등록</strong>
          </span>
        </Link>

        <Link
          to={ROUTE_PATHS.consultantNotices}
          role="tab"
          aria-selected={noticeActive}
          aria-controls="consultant-notice-panel"
          className={`consultant-work-tab consultant-work-tab--notice${
            noticeActive ? " is-active" : ""
          }`}
        >
          <span>
            <NoticeIcon />
            <strong>공지사항</strong>
          </span>
        </Link>

        <Link
          to={ROUTE_PATHS.consultantContacts}
          role="tab"
          aria-selected={contactsActive}
          aria-controls="consultant-contacts-panel"
          className={`consultant-work-tab consultant-work-tab--contacts${
            contactsActive ? " is-active" : ""
          }`}
        >
          <span>
            <ContactsIcon />
            <strong>직원 연락처</strong>
          </span>
        </Link>
      </nav>
    </aside>
  );
}

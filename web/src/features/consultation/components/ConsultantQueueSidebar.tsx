import { Link, useNavigate } from "react-router-dom";

import { ROUTE_PATHS } from "../../../app/router/routePaths";
import { WORK_BUCKET_LABELS } from "../model/consultantWorkspaceModel";
import type { CounselorWorkBucket } from "../model/consultantWorkspaceTypes";

export type ConsultantInquiryBucket = CounselorWorkBucket | "ALL";

const WORK_BUCKETS: readonly ConsultantInquiryBucket[] = [
  "ALL",
  "NEW",
  "IN_PROGRESS",
  "COMPLETED",
];

interface ConsultantQueueSidebarProps {
  activeBucket: ConsultantInquiryBucket | null;
  bucketCounts?: Readonly<Record<CounselorWorkBucket, number>>;
  dashboardActive?: boolean;
  noticeActive?: boolean;
  phoneEntryActive?: boolean;
  onBucketChange?: (bucket: ConsultantInquiryBucket) => void;
}

export default function ConsultantQueueSidebar({
  activeBucket,
  bucketCounts,
  dashboardActive = false,
  noticeActive = false,
  phoneEntryActive = false,
  onBucketChange,
}: ConsultantQueueSidebarProps) {
  const navigate = useNavigate();

  const openBucket = (bucket: ConsultantInquiryBucket) => {
    if (onBucketChange) {
      onBucketChange(bucket);
      return;
    }
    navigate(`${ROUTE_PATHS.consultantInquiryList}?bucket=${bucket}`);
  };

  return (
    <aside id="consultant-queue-sidebar" className="consultant-sidebar">
      <a
        className="simple-brand consultant-sidebar-brand"
        href="/"
        aria-label="Water Bridge 홈으로 이동"
      >
        <span className="simple-brand__wordmark" aria-hidden="true">
          <span className="simple-brand__wordmark-water">Water</span>
          <span className="simple-brand__wordmark-bridge">Bridge</span>
        </span>
      </a>

      <nav
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
              !phoneEntryActive &&
              activeBucket === bucket
            }
            aria-controls="consultant-queue-panel"
            className={`consultant-work-tab consultant-work-tab--${bucket.toLowerCase()}${
              !dashboardActive &&
              !noticeActive &&
              !phoneEntryActive &&
              activeBucket === bucket
                ? " is-active"
                : ""
            }`}
            onClick={() => openBucket(bucket)}
          >
            <span>
              <strong>{bucket === "ALL" ? "전체 문의" : WORK_BUCKET_LABELS[bucket]}</strong>
            </span>
            {bucketCounts && (
              <b>
                {bucket === "ALL"
                  ? bucketCounts.NEW +
                    bucketCounts.IN_PROGRESS +
                    bucketCounts.COMPLETED
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
            <strong>공지사항</strong>
          </span>
        </Link>
      </nav>
    </aside>
  );
}

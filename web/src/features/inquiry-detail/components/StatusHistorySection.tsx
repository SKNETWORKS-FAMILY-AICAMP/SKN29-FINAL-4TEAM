import type {
  InquiryDetailSectionStatus,
  StatusHistoryItem,
} from "../model/inquiryDetailTypes";
import InquirySectionError from "./InquirySectionError";

interface StatusHistorySectionProps {
  statusHistory: readonly StatusHistoryItem[];
  status: InquiryDetailSectionStatus;
}

export default function StatusHistorySection({
  statusHistory,
  status,
}: StatusHistorySectionProps) {
  return (
    <section className="inquiry-detail__card">
      <h2>상태 이력</h2>

      {status === "error" ? (
        <InquirySectionError
          title="상태 이력을 불러오지 못했습니다."
          description="현재 문의 정보와 상담 작성 기능은 계속 사용할 수 있습니다. 최신 이력은 잠시 후 다시 확인해 주세요."
        />
      ) : (
        <ol className="inquiry-detail__history">
          {statusHistory.map((history, index) => (
            <li key={`${history.status}-${history.occurredAt}`}>
              <div className="inquiry-detail__history-index">
                {index + 1}
              </div>

              <div>
                <strong>{history.status}</strong>
                <p>{history.event}</p>

                <span>
                  {history.actor} · {history.occurredAt}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

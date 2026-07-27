import { useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  createInquiryDetailPath,
  ROUTE_PATHS,
} from "../../app/router/routePaths";
import "./VisitTransitionPage.css";

interface VisitTransitionLocationState {
  stateVersion?: number;
  symptomSummary?: string;
}

type VisitReason =
  | "LEAK_SUSPECTED"
  | "REPEATED_SYMPTOM"
  | "REMOTE_RESOLUTION_FAILED"
  | "PRODUCT_INSPECTION_REQUIRED"
  | "OTHER";

const VISIT_REASON_LABELS: Record<VisitReason, string> = {
  LEAK_SUSPECTED: "누수 의심",
  REPEATED_SYMPTOM: "동일 증상 재발",
  REMOTE_RESOLUTION_FAILED: "상담 안내로 해결되지 않음",
  PRODUCT_INSPECTION_REQUIRED: "제품 현장 점검 필요",
  OTHER: "기타",
};

export default function VisitTransitionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { inquiryId } = useParams<{ inquiryId: string }>();

  const locationState =
    location.state as VisitTransitionLocationState | null;

  const stateVersion = locationState?.stateVersion ?? 1;
  const symptomSummary =
    locationState?.symptomSummary ?? "증상 정보 없음";

  const [visitReason, setVisitReason] =
    useState<VisitReason>("PRODUCT_INSPECTION_REQUIRED");
  const [preferredDate, setPreferredDate] = useState("");
  const [preferredTime, setPreferredTime] = useState("");
  const [handoffNote, setHandoffNote] = useState(
    "상담 내용을 확인한 뒤 제품 상태를 점검해 주세요.",
  );
  const [submitMessage, setSubmitMessage] = useState("");

  if (!inquiryId) {
    return (
      <main className="visit-transition">
        <section className="visit-transition__not-found">
          <p className="visit-transition__eyebrow">CONS-03</p>
          <h1>문의 정보가 없습니다.</h1>

          <button
            type="button"
            onClick={() =>
              navigate(ROUTE_PATHS.consultantInquiryList)
            }
          >
            문의 목록으로 돌아가기
          </button>
        </section>
      </main>
    );
  }

  const handleSubmit = () => {
    if (!preferredDate) {
      setSubmitMessage("희망 방문 날짜를 선택해 주세요.");
      return;
    }

    if (!preferredTime) {
      setSubmitMessage("희망 시간대를 선택해 주세요.");
      return;
    }

    if (handoffNote.trim().length === 0) {
      setSubmitMessage("기사 인계 내용을 입력해 주세요.");
      return;
    }

    setSubmitMessage(
      "Mock 방문 전환 요청이 완료되었습니다. 실제 기사 배정 및 일정 생성은 아직 이루어지지 않습니다.",
    );
  };

  return (
    <main className="visit-transition">
      <header className="visit-transition__header">
        <div>
          <p className="visit-transition__eyebrow">CONS-03</p>
          <h1>방문 전환·일정 등록</h1>
          <p>{inquiryId}</p>
        </div>

        <button
          type="button"
          className="visit-transition__back-button"
          onClick={() =>
            navigate(createInquiryDetailPath(inquiryId))
          }
        >
          문의 상세로 돌아가기
        </button>
      </header>

      <section className="visit-transition__summary">
        <article>
          <span>문의 번호</span>
          <strong>{inquiryId}</strong>
        </article>

        <article>
          <span>상태 버전</span>
          <strong>{stateVersion}</strong>
        </article>

        <article>
          <span>기사 배정 상태</span>
          <strong>배정 전</strong>
        </article>
      </section>

      <section className="visit-transition__card">
        <h2>고객 증상 요약</h2>
        <p>{symptomSummary}</p>
      </section>

      <section className="visit-transition__card">
        <h2>방문 전환 정보</h2>

        <div className="visit-transition__form-grid">
          <label>
            <span>방문 전환 사유</span>

            <select
              value={visitReason}
              onChange={(event) =>
                setVisitReason(event.target.value as VisitReason)
              }
            >
              {Object.entries(VISIT_REASON_LABELS).map(
                ([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ),
              )}
            </select>
          </label>

          <label>
            <span>희망 방문 날짜</span>

            <input
              type="date"
              value={preferredDate}
              onChange={(event) =>
                setPreferredDate(event.target.value)
              }
            />
          </label>

          <label>
            <span>희망 시간대</span>

            <select
              value={preferredTime}
              onChange={(event) =>
                setPreferredTime(event.target.value)
              }
            >
              <option value="">시간대 선택</option>
              <option value="09:00-12:00">
                오전 09:00~12:00
              </option>
              <option value="12:00-15:00">
                오후 12:00~15:00
              </option>
              <option value="15:00-18:00">
                오후 15:00~18:00
              </option>
            </select>
          </label>
        </div>

        <label className="visit-transition__textarea-label">
          <span>방문기사 인계 내용</span>

          <textarea
            value={handoffNote}
            onChange={(event) =>
              setHandoffNote(event.target.value)
            }
            rows={6}
            placeholder="상담 결과와 현장에서 확인할 사항을 입력하세요."
          />
        </label>

        <div className="visit-transition__meta">
          <span>방문 사유 코드: {visitReason}</span>
          <span>상태 버전: {stateVersion}</span>
        </div>

        <button
          type="button"
          className="visit-transition__submit-button"
          onClick={handleSubmit}
        >
          방문 요청 등록
        </button>

        {submitMessage && (
          <p
            className="visit-transition__message"
            aria-live="polite"
          >
            {submitMessage}
          </p>
        )}

        <p className="visit-transition__mock-notice">
          현재는 Mock 화면입니다. 실제 방문 요청 API는 아직
          연결되지 않았습니다.
        </p>
      </section>
    </main>
  );
}

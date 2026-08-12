import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "../../app/providers/authContext";
import consultantAvatar from "../../assets/images/water-bridge-consultant.png";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import {
  phoneInquiryLocalRepository,
  type PhoneInquiryRecord,
  type PhoneInquiryUrgency,
} from "../../features/consultation/repositories/phoneInquiryLocalRepository";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";
import "../../common/styles/water-glass-theme.css";
import "./ConsultantOperationsTone.css";
import "./PhoneInquiryCreatePage.css";

const INQUIRY_CATEGORIES = [
  "제품 사용 문의",
  "누수·안전 문의",
  "출수·온도 이상",
  "필터·위생 문의",
  "소음·진동 문의",
  "방문 점검 요청",
  "기타 문의",
] as const;

interface PhoneInquiryFormState {
  customerName: string;
  phoneNumber: string;
  category: string;
  productModel: string;
  inquiryContent: string;
  consultationNote: string;
  urgency: PhoneInquiryUrgency;
  callbackRequired: boolean;
  privacyConfirmed: boolean;
}

const INITIAL_FORM: PhoneInquiryFormState = {
  customerName: "",
  phoneNumber: "",
  category: "",
  productModel: "",
  inquiryContent: "",
  consultationNote: "",
  urgency: "GENERAL",
  callbackRequired: false,
  privacyConfirmed: false,
};

const URGENCY_LABELS: Record<PhoneInquiryUrgency, string> = {
  GENERAL: "일반",
  CAUTION: "주의",
  URGENT: "긴급",
};

function formatRecordTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function PhoneInquiryCreatePage() {
  const { user } = useAuth();
  const [form, setForm] = useState<PhoneInquiryFormState>(INITIAL_FORM);
  const [records, setRecords] = useState<readonly PhoneInquiryRecord[]>(() =>
    phoneInquiryLocalRepository.list(),
  );
  const [savedRecord, setSavedRecord] = useState<PhoneInquiryRecord | null>(
    null,
  );

  useEffect(() => {
    document.body.classList.add("compact-consultant-body");
    return () => document.body.classList.remove("compact-consultant-body");
  }, []);

  const updateForm = <TKey extends keyof PhoneInquiryFormState>(
    key: TKey,
    value: PhoneInquiryFormState[TKey],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const submitPhoneInquiry = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const record = phoneInquiryLocalRepository.create({
      customerName: form.customerName.trim(),
      phoneNumber: form.phoneNumber.trim(),
      category: form.category,
      productModel: form.productModel.trim(),
      inquiryContent: form.inquiryContent.trim(),
      consultationNote: form.consultationNote.trim(),
      urgency: form.urgency,
      callbackRequired: form.callbackRequired,
      counselorName: user?.displayName ?? "상담사",
    });
    setRecords(phoneInquiryLocalRepository.list());
    setSavedRecord(record);
    setForm(INITIAL_FORM);
  };

  return (
    <div className="simple-consultant-app consultant-queue-app phone-inquiry-entry-app">
      <main className="simple-consultant-main consultant-queue-main">
        <header className="simple-topbar consultant-main-header phone-inquiry-main-header">
          <div className="phone-inquiry-main-header__copy">
            <small>CALL INTAKE</small>
            <h1>전화 문의 등록</h1>
            <p>앱을 사용하지 않는 고객의 상담 내용을 직접 기록합니다.</p>
          </div>

          <div className="simple-user">
            <span className="simple-user__avatar-frame" aria-hidden="true">
              <img
                className="simple-user__avatar-image"
                src={consultantAvatar}
                alt=""
              />
            </span>
            <strong className="simple-user__name">
              {user?.displayName ?? "상담사"}
            </strong>
          </div>
        </header>

        <ConsultantQueueSidebar activeBucket={null} phoneEntryActive />

        <section
          id="consultant-phone-entry-panel"
          className="consultant-queue-panel phone-inquiry-entry-panel"
          role="tabpanel"
          aria-label="전화 문의 등록"
        >
          <div className="phone-inquiry-entry-layout">
            <form
              className="phone-inquiry-form-card"
              onSubmit={submitPhoneInquiry}
            >
              <header className="phone-inquiry-card-head">
                <div>
                  <span>신규 접수</span>
                  <h2>고객과 통화한 내용을 입력해 주세요</h2>
                </div>
                <small>필수 항목 *</small>
              </header>

              {savedRecord && (
                <div className="phone-inquiry-save-notice" role="status">
                  <strong>{savedRecord.customerName}</strong> 고객의 전화 문의가
                  임시 저장되었습니다.
                </div>
              )}

              <div className="phone-inquiry-form-grid">
                <label>
                  <span>고객명 *</span>
                  <input
                    required
                    value={form.customerName}
                    onChange={(event) =>
                      updateForm("customerName", event.target.value)
                    }
                    placeholder="고객 이름"
                  />
                </label>

                <label>
                  <span>연락처 *</span>
                  <input
                    required
                    type="tel"
                    inputMode="tel"
                    pattern="[0-9-]{9,13}"
                    value={form.phoneNumber}
                    onChange={(event) =>
                      updateForm("phoneNumber", event.target.value)
                    }
                    placeholder="010-0000-0000"
                  />
                </label>

                <label>
                  <span>문의 유형 *</span>
                  <select
                    required
                    value={form.category}
                    onChange={(event) =>
                      updateForm("category", event.target.value)
                    }
                  >
                    <option value="">문의 유형 선택</option>
                    {INQUIRY_CATEGORIES.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>제품 모델</span>
                  <input
                    value={form.productModel}
                    onChange={(event) =>
                      updateForm("productModel", event.target.value)
                    }
                    placeholder="예: WPU-JAC104D"
                  />
                </label>

                <fieldset className="phone-inquiry-urgency">
                  <legend>문의 구분 *</legend>
                  {(
                    Object.entries(URGENCY_LABELS) as readonly [
                      PhoneInquiryUrgency,
                      string,
                    ][]
                  ).map(([value, label]) => (
                    <label key={value}>
                      <input
                        type="radio"
                        name="phone-inquiry-urgency"
                        value={value}
                        checked={form.urgency === value}
                        onChange={() => updateForm("urgency", value)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </fieldset>

                <label className="phone-inquiry-field--wide">
                  <span>문의 내용 *</span>
                  <textarea
                    required
                    rows={4}
                    value={form.inquiryContent}
                    onChange={(event) =>
                      updateForm("inquiryContent", event.target.value)
                    }
                    placeholder="고객이 설명한 증상과 요청 사항을 그대로 기록해 주세요."
                  />
                </label>

                <label className="phone-inquiry-field--wide">
                  <span>상담 기록</span>
                  <textarea
                    rows={3}
                    value={form.consultationNote}
                    onChange={(event) =>
                      updateForm("consultationNote", event.target.value)
                    }
                    placeholder="안내한 내용, 확인 사항, 후속 조치를 기록해 주세요."
                  />
                </label>

                <div className="phone-inquiry-checks phone-inquiry-field--wide">
                  <label>
                    <input
                      type="checkbox"
                      checked={form.callbackRequired}
                      onChange={(event) =>
                        updateForm("callbackRequired", event.target.checked)
                      }
                    />
                    <span>추가 회신이 필요합니다.</span>
                  </label>
                  <label>
                    <input
                      required
                      type="checkbox"
                      checked={form.privacyConfirmed}
                      onChange={(event) =>
                        updateForm("privacyConfirmed", event.target.checked)
                      }
                    />
                    <span>고객에게 개인정보 수집·이용 안내를 완료했습니다. *</span>
                  </label>
                </div>
              </div>

              <footer className="phone-inquiry-form-actions">
                <button
                  type="button"
                  className="phone-inquiry-button phone-inquiry-button--secondary"
                  onClick={() => {
                    setForm(INITIAL_FORM);
                    setSavedRecord(null);
                  }}
                >
                  입력 초기화
                </button>
                <button
                  type="submit"
                  className="phone-inquiry-button phone-inquiry-button--primary"
                >
                  전화 문의 저장
                </button>
              </footer>
            </form>

            <aside
              className="phone-inquiry-recent-card"
              aria-label="최근 전화 문의 접수 내역"
            >
              <header>
                <div>
                  <span>최근 기록</span>
                  <h2>전화 문의 접수 내역</h2>
                </div>
                <b>{records.length}</b>
              </header>

              <p className="phone-inquiry-local-note">
                Backend 생성 API 연동 전까지 이 브라우저에 임시 저장됩니다.
              </p>

              <div className="phone-inquiry-recent-list">
                {records.length === 0 ? (
                  <p className="phone-inquiry-recent-empty">
                    아직 등록된 전화 문의가 없습니다.
                  </p>
                ) : (
                  records.map((record) => (
                    <article key={record.id}>
                      <div>
                        <span
                          className={`phone-inquiry-urgency-badge phone-inquiry-urgency-badge--${record.urgency.toLowerCase()}`}
                        >
                          {URGENCY_LABELS[record.urgency]}
                        </span>
                        <time dateTime={record.createdAt}>
                          {formatRecordTime(record.createdAt)}
                        </time>
                      </div>
                      <h3>{record.customerName}</h3>
                      <small>{record.phoneNumber}</small>
                      <strong>{record.category}</strong>
                      <p>{record.inquiryContent}</p>
                    </article>
                  ))
                )}
              </div>
            </aside>
          </div>
        </section>
      </main>
    </div>
  );
}

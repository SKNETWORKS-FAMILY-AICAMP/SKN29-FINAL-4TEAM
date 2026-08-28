import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";

import { appEnv } from "../../app/config/env";
import { createInquiryDetailPath } from "../../app/router/routePaths";
import { ApiClientError } from "../../common/api/apiError";
import { IdempotencyOperationTracker } from "../../common/api/idempotencyOperation";
import { createRequestContext } from "../../common/api/requestContext";
import { parseInquiryId } from "../../entities/inquiry/inquiryIdentifiers";
import type {
  ConsultantInquiryListQuery,
  ConsultantInquiryStatusDto,
} from "../../features/consultation/api/consultantWorkspaceRemoteTypes";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantHeaderBrand from "../../features/consultation/components/ConsultantHeaderBrand";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import { useConsultantInquiryListQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import type { CounselorWorkBucket } from "../../features/consultation/model/consultantWorkspaceTypes";
import {
  consultantWorkspaceDataRepository,
  createMockConsultantInquiryListViewModel,
} from "../../features/consultation/repositories/consultantWorkspaceDataRepository";
import { getManagementTypeLabel } from "../../features/consultation/model/consultantWorkspaceRemoteMapper";
import { formatProductModelAndName } from "../../features/consultation/model/productDisplayName";
import {
  phoneInquiryRemoteRepository,
  type CustomerSubscriptionCandidateDto,
  type PhoneInquiryPriorityCode,
  type PhoneInquirySymptomCode,
  type RegisterPhoneInquiryResultDto,
} from "../../features/consultation/repositories/phoneInquiryRemoteRepository";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";
import "../../common/styles/water-glass-theme.css";
import "./ConsultantOperationsTone.css";
import "./PhoneInquiryCreatePage.css";

const SEARCH_DELAY_MS = 300;
const PHONE_LIKE_PATTERN = /^[0-9\s()+-]+$/;
// The current Backend contract still requires priority_code after the UI choice is removed.
const DEFAULT_PHONE_INQUIRY_PRIORITY: PhoneInquiryPriorityCode = "NORMAL";

const SIDEBAR_BUCKET_STATUSES: Record<
  CounselorWorkBucket,
  readonly ConsultantInquiryStatusDto[]
> = {
  NEW: ["CONSULTATION_REQUIRED", "REOPENED"],
  IN_PROGRESS: [
    "DRAFT",
    "QUESTIONNAIRE_IN_PROGRESS",
    "AI_GUIDANCE",
    "CONSULTATION_IN_PROGRESS",
    "VISIT_REVIEW_PENDING",
    "VISIT_SCHEDULING",
    "VISIT_SCHEDULED",
    "COMPLETION_PENDING",
    "REVISIT_REQUIRED",
  ],
  COMPLETED: ["RESOLVED", "CANCELLED"],
};

const SYMPTOM_LABELS: Readonly<Record<PhoneInquirySymptomCode, string>> = {
  NO_WATER: "출수 안 됨",
  LOW_FLOW: "출수량 저하",
  LEAK: "누수",
  ODOR: "냄새",
  TASTE: "맛 이상",
  TEMPERATURE_ABNORMAL: "온도 이상",
  NOISE: "소음",
  DISPLAY_ERROR: "표시부 오류",
  OTHER: "기타",
};

interface PhoneInquiryFormState {
  rawText: string;
  symptomCode: PhoneInquirySymptomCode | "";
}

type SearchState = "IDLE" | "LOADING" | "RESULTS" | "EMPTY" | "ERROR";

const INITIAL_FORM: PhoneInquiryFormState = {
  rawText: "",
  symptomCode: "",
};

function isEligibleSearchQuery(value: string): boolean {
  const normalized = value.trim();
  if (PHONE_LIKE_PATTERN.test(normalized)) {
    return normalized.replace(/\D/g, "").length >= 4;
  }
  return normalized.length >= 2;
}

function getErrorMessage(error: unknown, action: "SEARCH" | "REGISTER"): string {
  if (!(error instanceof ApiClientError)) {
    return action === "SEARCH"
      ? "고객 정보를 불러오지 못했습니다. 다시 시도해 주세요."
      : "전화 문의를 등록하지 못했습니다. 다시 시도해 주세요.";
  }

  if (error.status === 403) return "상담사 권한으로만 사용할 수 있는 기능입니다.";
  if (error.status === 422) return error.message;
  if (error.status === 409) {
    return "이전 등록 요청과 멱등 키가 충돌했습니다. 새 요청으로 다시 시도해 주세요.";
  }
  if (error.status === 404) {
    return "선택한 구독이 더 이상 유효하지 않습니다. 고객을 다시 검색해 주세요.";
  }

  const baseMessage =
    action === "SEARCH"
      ? "고객 정보를 불러오지 못했습니다. 다시 시도해 주세요."
      : "전화 문의를 등록하지 못했습니다. 입력 내용을 유지했습니다.";
  return error.correlationId
    ? `${baseMessage} Correlation ID: ${error.correlationId}`
    : baseMessage;
}

function candidateOptionId(subscriptionId: string): string {
  return `phone-customer-option-${subscriptionId}`;
}

export default function PhoneInquiryCreatePage() {
  const sidebarRepositoryQuery = useMemo<ConsultantInquiryListQuery>(
    () => ({
      status: [
        ...SIDEBAR_BUCKET_STATUSES.NEW,
        ...SIDEBAR_BUCKET_STATUSES.IN_PROGRESS,
        ...SIDEBAR_BUCKET_STATUSES.COMPLETED,
      ],
      page: 1,
      size: 100,
    }),
    [],
  );
  const sidebarQuery = useConsultantInquiryListQuery(sidebarRepositoryQuery);
  const remoteSidebarHasEmptyBucket =
    sidebarQuery.status === "success" &&
    Object.values(SIDEBAR_BUCKET_STATUSES).some(
      (statuses) =>
        !sidebarQuery.data?.items.some((inquiry) =>
          statuses.includes(inquiry.status),
        ),
    );
  const useSidebarDesignMockFallback =
    appEnv.enableDesignMockFallback &&
    import.meta.env.DEV &&
    consultantWorkspaceDataRepository.dataSource === "REMOTE" &&
    (sidebarQuery.status === "error" || remoteSidebarHasEmptyBucket);
  const sidebarData = useMemo(
    () =>
      useSidebarDesignMockFallback
        ? createMockConsultantInquiryListViewModel(
            sidebarRepositoryQuery,
            "DESIGN_SCENARIOS",
          )
        : consultantWorkspaceDataRepository.dataSource === "MOCK"
          ? createMockConsultantInquiryListViewModel(sidebarRepositoryQuery)
          : sidebarQuery.data,
    [sidebarQuery.data, sidebarRepositoryQuery, useSidebarDesignMockFallback],
  );
  const sidebarBucketCounts = useMemo(
    () =>
      sidebarData
        ? (Object.fromEntries(
            Object.entries(SIDEBAR_BUCKET_STATUSES).map(
              ([bucket, statuses]) => [
                bucket,
                statuses.reduce(
                  (total, status) =>
                    total + (sidebarData.statusCounts[status] ?? 0),
                  0,
                ),
              ],
            ),
          ) as Record<CounselorWorkBucket, number>)
        : undefined,
    [sidebarData],
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [searchRetry, setSearchRetry] = useState(0);
  const [searchState, setSearchState] = useState<SearchState>("IDLE");
  const [searchError, setSearchError] = useState("");
  const [candidates, setCandidates] = useState<
    readonly CustomerSubscriptionCandidateDto[]
  >([]);
  const [isCandidatePanelOpen, setIsCandidatePanelOpen] = useState(false);
  const [activeCandidateIndex, setActiveCandidateIndex] = useState(-1);
  const [selectedCandidate, setSelectedCandidate] =
    useState<CustomerSubscriptionCandidateDto | null>(null);
  const [form, setForm] = useState<PhoneInquiryFormState>(INITIAL_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [registeredInquiry, setRegisteredInquiry] =
    useState<RegisterPhoneInquiryResultDto | null>(null);
  const operationTrackerRef = useRef(new IdempotencyOperationTracker());

  useEffect(() => {
    document.body.classList.add("compact-consultant-body");
    return () => document.body.classList.remove("compact-consultant-body");
  }, []);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!isEligibleSearchQuery(query)) return;

    let cancelled = false;

    const timer = window.setTimeout(async () => {
      try {
        const result =
          await phoneInquiryRemoteRepository.searchCustomerSubscriptions(query);
        if (cancelled) return;
        setCandidates(result.data.items);
        setSearchState(result.data.items.length > 0 ? "RESULTS" : "EMPTY");
        setActiveCandidateIndex(result.data.items.length > 0 ? 0 : -1);
      } catch (error) {
        if (cancelled) return;
        setCandidates([]);
        setSearchState("ERROR");
        setSearchError(getErrorMessage(error, "SEARCH"));
        setActiveCandidateIndex(-1);
      }
    }, SEARCH_DELAY_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [searchQuery, searchRetry]);

  const updateForm = <TKey extends keyof PhoneInquiryFormState>(
    key: TKey,
    value: PhoneInquiryFormState[TKey],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
    setSubmitError("");
    setRegisteredInquiry(null);
  };

  const selectCandidate = (candidate: CustomerSubscriptionCandidateDto) => {
    setSelectedCandidate(candidate);
    setIsCandidatePanelOpen(false);
    setSubmitError("");
    setRegisteredInquiry(null);
    operationTrackerRef.current.finish();
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setIsCandidatePanelOpen(false);
      return;
    }
    if (searchState !== "RESULTS" || candidates.length === 0) return;

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setIsCandidatePanelOpen(true);
      setActiveCandidateIndex((current) => {
        if (event.key === "ArrowDown") return (current + 1) % candidates.length;
        return (current - 1 + candidates.length) % candidates.length;
      });
      return;
    }
    if (event.key === "Enter" && isCandidatePanelOpen) {
      event.preventDefault();
      const candidate = candidates[activeCandidateIndex];
      if (candidate) selectCandidate(candidate);
    }
  };

  const resetSelection = () => {
    setSelectedCandidate(null);
    setRegisteredInquiry(null);
    setSubmitError("");
    setCandidates([]);
    setSearchQuery("");
    setSearchState("IDLE");
    setForm(INITIAL_FORM);
    operationTrackerRef.current.finish();
  };

  const submitPhoneInquiry = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCandidate || !form.symptomCode || !form.rawText.trim()) return;

    const body = {
      subscription_id: selectedCandidate.subscription_id,
      raw_text: form.rawText.trim(),
      representative_symptom_code: form.symptomCode,
      priority_code: DEFAULT_PHONE_INQUIRY_PRIORITY,
    };
    const signature = JSON.stringify(body);
    const idempotencyKey = operationTrackerRef.current.begin(signature);

    setIsSubmitting(true);
    setSubmitError("");
    setRegisteredInquiry(null);
    try {
      const result = await phoneInquiryRemoteRepository.registerPhoneInquiry(
        body,
        createRequestContext({ idempotencyKey }),
      );
      operationTrackerRef.current.finish();
      setRegisteredInquiry(result.data);
      sidebarQuery.retry();
    } catch (error) {
      const retryable =
        error instanceof ApiClientError &&
        (error.kind === "NETWORK_ERROR" ||
          error.kind === "TIMEOUT" ||
          error.kind === "SERVER_ERROR");
      operationTrackerRef.current.fail(retryable);

      if (error instanceof ApiClientError && error.status === 404) {
        setSelectedCandidate(null);
        setCandidates([]);
        setSearchState("IDLE");
      }
      setSubmitError(getErrorMessage(error, "REGISTER"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeDescendant =
    isCandidatePanelOpen && activeCandidateIndex >= 0
      ? candidateOptionId(candidates[activeCandidateIndex]?.subscription_id ?? "")
      : undefined;

  return (
    <div className="simple-consultant-app consultant-queue-app phone-inquiry-entry-app">
      <main className="simple-consultant-main consultant-queue-main">
        <header className="simple-topbar consultant-main-header phone-inquiry-main-header consultant-unified-header">
          <ConsultantHeaderBrand />
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={null}
          bucketCounts={sidebarBucketCounts}
          phoneEntryActive
        />

        <section
          id="consultant-phone-entry-panel"
          className="consultant-queue-panel phone-inquiry-entry-panel"
          role="tabpanel"
          aria-label="전화 문의 등록"
        >
          <div className="phone-inquiry-entry-layout">
            <form className="phone-inquiry-form-card" onSubmit={submitPhoneInquiry}>
              <header className="phone-inquiry-card-head">
                <h2>전화 문의 등록</h2>
              </header>

              <div className="phone-inquiry-customer-search">
                <label htmlFor="phone-customer-search">고객명 또는 연락처 *</label>
                <div className="phone-inquiry-combobox">
                  <input
                    id="phone-customer-search"
                    role="combobox"
                    autoComplete="off"
                    aria-autocomplete="list"
                    aria-controls="phone-customer-options"
                    aria-expanded={isCandidatePanelOpen}
                    aria-activedescendant={activeDescendant}
                    value={searchQuery}
                    onChange={(event) => {
                      const nextQuery = event.target.value;
                      const isEligible = isEligibleSearchQuery(nextQuery);
                      setSearchQuery(nextQuery);
                      setSelectedCandidate(null);
                      setRegisteredInquiry(null);
                      setSubmitError("");
                      setCandidates([]);
                      setSearchError("");
                      setSearchState(isEligible ? "LOADING" : "IDLE");
                      setIsCandidatePanelOpen(isEligible);
                      setActiveCandidateIndex(-1);
                      operationTrackerRef.current.finish();
                    }}
                    onFocus={() => {
                      if (searchState !== "IDLE") setIsCandidatePanelOpen(true);
                    }}
                    onKeyDown={handleSearchKeyDown}
                    placeholder="이름 2자 이상 또는 연락처 숫자 4자리 이상"
                  />

                  {isCandidatePanelOpen && (
                    <div
                      id="phone-customer-options"
                      className="phone-inquiry-candidate-panel"
                      role="listbox"
                      aria-label="기존 구독 고객 검색 결과"
                    >
                      {searchState === "LOADING" && (
                        <p role="status">고객을 검색하고 있습니다.</p>
                      )}
                      {searchState === "EMPTY" && (
                        <p>일치하는 구독 고객이 없습니다. 이름 또는 연락처를 다시 확인해 주세요.</p>
                      )}
                      {searchState === "ERROR" && (
                        <div className="phone-inquiry-search-error" role="alert">
                          <p>{searchError}</p>
                          <button
                            type="button"
                            onClick={() => {
                              setSearchState("LOADING");
                              setSearchError("");
                              setSearchRetry((value) => value + 1);
                            }}
                          >
                            다시 시도
                          </button>
                        </div>
                      )}
                      {searchState === "RESULTS" &&
                        candidates.map((candidate, index) => (
                          <button
                            id={candidateOptionId(candidate.subscription_id)}
                            key={candidate.subscription_id}
                            type="button"
                            role="option"
                            aria-selected={index === activeCandidateIndex}
                            className={index === activeCandidateIndex ? "is-active" : ""}
                            onMouseEnter={() => setActiveCandidateIndex(index)}
                            onClick={() => selectCandidate(candidate)}
                          >
                            <span>
                              <strong>{candidate.customer_display_name}</strong>
                              <small>{candidate.phone_masked}</small>
                            </span>
                            <span>
                              <b>
                                {formatProductModelAndName(
                                  candidate.product_model_code,
                                  candidate.product_name,
                                )}
                              </b>
                              <small>이용 중</small>
                            </span>
                          </button>
                        ))}
                    </div>
                  )}
                </div>
                {!isEligibleSearchQuery(searchQuery) && searchQuery.length > 0 && (
                  <small className="phone-inquiry-search-hint">
                    이름은 2자 이상, 연락처는 숫자 4자리 이상 입력해 주세요.
                  </small>
                )}
              </div>

              {selectedCandidate && (
                <section className="phone-inquiry-selected-card" aria-label="고객 정보">
                  <div>
                    <span>고객 정보</span>
                    <strong>{selectedCandidate.customer_display_name}</strong>
                    <small>{selectedCandidate.phone_masked}</small>
                  </div>
                  <dl>
                    <div>
                      <dt>제품</dt>
                      <dd>
                        {formatProductModelAndName(
                          selectedCandidate.product_model_code,
                          selectedCandidate.product_name,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>관리 유형</dt>
                      <dd>
                        {getManagementTypeLabel(
                          selectedCandidate.management_type_code,
                        )}
                      </dd>
                    </div>
                  </dl>
                  <button type="button" onClick={resetSelection}>다른 고객 선택</button>
                </section>
              )}

              <fieldset className="phone-inquiry-details" disabled={!selectedCandidate || isSubmitting}>
                <legend>전화 문의 내용</legend>

                <label>
                  <span>대표 증상 *</span>
                  <span className="phone-inquiry-select-control">
                    <select
                      required
                      value={form.symptomCode}
                      onChange={(event) =>
                        updateForm("symptomCode", event.target.value as PhoneInquirySymptomCode | "")
                      }
                    >
                      <option value="">대표 증상을 선택해 주세요</option>
                      {(Object.entries(SYMPTOM_LABELS) as readonly [PhoneInquirySymptomCode, string][]).map(
                        ([code, label]) => <option key={code} value={code}>{label}</option>,
                      )}
                    </select>
                    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
                      <path d="m7 9.5 5 5 5-5" />
                    </svg>
                  </span>
                </label>

                <label className="phone-inquiry-field--wide">
                  <span>문의 내용 *</span>
                  <textarea
                    required
                    minLength={1}
                    maxLength={5000}
                    rows={6}
                    value={form.rawText}
                    onChange={(event) => updateForm("rawText", event.target.value)}
                    placeholder="고객이 설명한 증상과 요청 사항을 기록해 주세요."
                  />
                  <small>{form.rawText.length.toLocaleString()} / 5,000</small>
                </label>

              </fieldset>

              {submitError && <div className="phone-inquiry-submit-error" role="alert">{submitError}</div>}
              {registeredInquiry && (
                <div className="phone-inquiry-save-notice">
                  <div role="status">
                    <strong>{registeredInquiry.inquiry_code}</strong>
                    <span> 전화 문의가 새 문의로 등록되었습니다.</span>
                  </div>
                  <div className="phone-inquiry-save-actions">
                    <button
                      type="button"
                      className="phone-inquiry-button phone-inquiry-button--secondary"
                      onClick={resetSelection}
                    >
                      새 문의 등록
                    </button>
                    <Link
                      className="phone-inquiry-button phone-inquiry-button--primary"
                      to={createInquiryDetailPath(
                        parseInquiryId(registeredInquiry.inquiry_id),
                      )}
                    >
                      문의 상세 보기
                    </Link>
                  </div>
                </div>
              )}

              {!registeredInquiry && (
                <footer className="phone-inquiry-form-actions">
                  <button
                    type="button"
                    className="phone-inquiry-button phone-inquiry-button--secondary"
                    onClick={resetSelection}
                  >
                    입력 초기화
                  </button>
                  <button
                    type="submit"
                    className="phone-inquiry-button phone-inquiry-button--primary"
                    disabled={
                      !selectedCandidate ||
                      !form.symptomCode ||
                      !form.rawText.trim() ||
                      isSubmitting
                    }
                  >
                    {isSubmitting ? "등록 중..." : "전화 문의 등록"}
                  </button>
                </footer>
              )}
            </form>
          </div>
        </section>
      </main>
    </div>
  );
}

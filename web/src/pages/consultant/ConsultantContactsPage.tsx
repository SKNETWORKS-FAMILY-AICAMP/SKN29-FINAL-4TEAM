import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTE_PATHS } from "../../app/router/routePaths";
import { ApiClientError } from "../../common/api/apiError";
import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import FormSelect from "../../common/components/form/FormSelect";
import ConsultantHeaderBrand from "../../features/consultation/components/ConsultantHeaderBrand";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import { useConsultantSidebarSummary } from "../../features/consultation/hooks/useConsultantSidebarSummary";
import { getSyntheticConsultantDashboardData } from "../../features/notice/api/consultantNoticeApi";
import type { SyntheticConsultantDashboardData } from "../../features/notice/model/consultantNotice";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";
import "../../common/styles/water-glass-theme.css";
import "./ConsultantOperationsTone.css";
import "./ConsultantWorkDashboard.css";
import "./ConsultantDirectoryLayout.css";
import "./ConsultantContactsPage.css";

type ContactKind = "CONSULTANT" | "TECHNICIAN";
type ContactKindFilter = "ALL" | ContactKind;
type ContactLoadState = "loading" | "ready" | "unauthorized" | "forbidden" | "error";
type ContactData = Pick<SyntheticConsultantDashboardData, "consultants" | "technicians">;

interface ContactRow {
  id: string;
  name: string;
  kind: ContactKind;
  department: string;
  position: string;
  phone: string;
  email: string;
}

interface OrganizationGroup {
  id: string;
  kind: ContactKind;
  department: string;
  contacts: readonly ContactRow[];
  roleSummary: string;
}

const CONTACT_KIND_FILTERS: readonly { value: ContactKindFilter; label: string }[] = [
  { value: "ALL", label: "전체 연락처" },
  { value: "CONSULTANT", label: "직원" },
  { value: "TECHNICIAN", label: "방문기사" },
];

function normalizeContactSearch(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase().replace(/[-\s.()]+/g, "");
}

function ContactValue({ name, label, value, href, onCopy }: {
  name: string;
  label: string;
  value: string;
  href: string;
  onCopy: (value: string, label: string) => Promise<void>;
}) {
  return (
    <span className="consultant-contact-value">
      {value.trim() ? (
        <a href={href} aria-label={`${name} ${label} 연결`}>{value}</a>
      ) : (
        <span>미등록</span>
      )}
      {value.trim() && (
        <button
          type="button"
          aria-label={`${name} ${label} 복사`}
          title={`${label} 복사`}
          onClick={() => { void onCopy(value, `${name} ${label}`); }}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <rect x="8" y="8" width="12" height="12" rx="2" />
            <path d="M15 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3" />
          </svg>
        </button>
      )}
    </span>
  );
}

function summarizeRoles(contacts: readonly ContactRow[]): string {
  const roleCounts = new Map<string, number>();
  contacts.forEach((contact) => {
    roleCounts.set(contact.position, (roleCounts.get(contact.position) ?? 0) + 1);
  });
  return [...roleCounts.entries()]
    .map(([role, count]) => `${role} ${count}`)
    .join(" · ");
}

function toOrganizationGroups(contacts: readonly ContactRow[]): OrganizationGroup[] {
  const groupedContacts = new Map<string, ContactRow[]>();
  contacts.forEach((contact) => {
    const key = `${contact.kind}:${contact.department}`;
    groupedContacts.set(key, [...(groupedContacts.get(key) ?? []), contact]);
  });

  return [...groupedContacts.entries()]
    .map(([id, grouped]) => ({
      id,
      kind: grouped[0].kind,
      department: grouped[0].department,
      contacts: grouped,
      roleSummary: summarizeRoles(grouped),
    }))
    .sort((left, right) =>
      (left.kind === right.kind ? 0 : left.kind === "CONSULTANT" ? -1 : 1) ||
      left.department.localeCompare(right.department, "ko"),
    );
}

function toContactRows(data: ContactData | null): ContactRow[] {
  if (!data) return [];
  return [
    ...data.consultants.map((person) => ({
      id: `consultant:${person.userId}`,
      name: person.name,
      kind: "CONSULTANT" as const,
      department: person.department,
      position: person.position,
      phone: person.extension,
      email: person.email,
    })),
    ...data.technicians.map((person) => ({
      id: `technician:${person.userId}`,
      name: person.name,
      kind: "TECHNICIAN" as const,
      department: person.branch,
      position: "방문기사",
      phone: person.phone,
      email: person.email,
    })),
  ].sort((left, right) =>
    (left.kind === right.kind ? 0 : left.kind === "CONSULTANT" ? -1 : 1) ||
    left.department.localeCompare(right.department, "ko") ||
    left.name.localeCompare(right.name, "ko"),
  );
}

export default function ConsultantContactsPage() {
  const navigate = useNavigate();
  const sidebarSummary = useConsultantSidebarSummary();
  const [data, setData] = useState<ContactData | null>(null);
  const [loadState, setLoadState] = useState<ContactLoadState>("loading");
  const [retryCount, setRetryCount] = useState(0);
  const [kindFilter, setKindFilter] = useState<ContactKindFilter>("ALL");
  const [departmentFilter, setDepartmentFilter] = useState("ALL");
  const [searchDraft, setSearchDraft] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [copyFeedback, setCopyFeedback] = useState("");

  useEffect(() => {
    let active = true;
    getSyntheticConsultantDashboardData().then(
      (result) => {
        if (!active) return;
        setData({ consultants: result.consultants, technicians: result.technicians });
        setDepartmentFilter((current) => current === "ALL" ||
          toContactRows(result).some((contact) => contact.department === current) ? current : "ALL");
        setLoadState("ready");
      },
      (error: unknown) => {
        if (!active) return;
        setData(null);
        setLoadState(
          error instanceof ApiClientError && error.status === 401
            ? "unauthorized"
            : error instanceof ApiClientError && error.status === 403
              ? "forbidden"
              : "error",
        );
      },
    );
    return () => { active = false; };
  }, [retryCount]);

  const contacts = useMemo(() => toContactRows(data), [data]);
  const organizationGroups = useMemo(
    () => toOrganizationGroups(contacts),
    [contacts],
  );
  const consultantGroups = useMemo(
    () => organizationGroups.filter((group) => group.kind === "CONSULTANT"),
    [organizationGroups],
  );
  const technicianGroups = useMemo(
    () => organizationGroups.filter((group) => group.kind === "TECHNICIAN"),
    [organizationGroups],
  );
  const kindContacts = useMemo(
    () => contacts.filter((contact) => kindFilter === "ALL" || contact.kind === kindFilter),
    [contacts, kindFilter],
  );
  const departments = useMemo(
    () => [...new Set(kindContacts.map((contact) => contact.department))]
      .filter(Boolean)
      .sort((left, right) => left.localeCompare(right, "ko")),
    [kindContacts],
  );
  const visibleContacts = useMemo(() => kindContacts.filter((contact) => {
    const matchesDepartment = departmentFilter === "ALL" || contact.department === departmentFilter;
    const searchableText = normalizeContactSearch(
      [contact.name, contact.department, contact.position, contact.phone, contact.email].join(" "),
    );
    return matchesDepartment && (!searchQuery || searchableText.includes(searchQuery));
  }), [departmentFilter, kindContacts, searchQuery]);
  const ready = loadState === "ready";
  const hasFilters = kindFilter !== "ALL" || departmentFilter !== "ALL" || Boolean(searchDraft || searchQuery);
  const resetFilters = () => {
    setKindFilter("ALL");
    setDepartmentFilter("ALL");
    setSearchDraft("");
    setSearchQuery("");
  };
  const selectOrganizationGroup = (group: OrganizationGroup) => {
    setKindFilter(group.kind);
    setDepartmentFilter(group.department);
    setSearchDraft("");
    setSearchQuery("");
  };
  const refreshContacts = () => {
    setCopyFeedback("");
    setLoadState("loading");
    setRetryCount((count) => count + 1);
  };
  const copyContact = async (value: string, label: string) => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard is unavailable");
      await navigator.clipboard.writeText(value);
      setCopyFeedback(`${label} 복사 완료`);
    } catch {
      setCopyFeedback("복사하지 못했습니다. 내용을 직접 선택해 복사해 주세요.");
    }
  };

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-contacts-app consultant-directory-app">
      <main className="simple-consultant-main consultant-queue-main">
        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantHeaderBrand />
          <ConsultantUserMenu className="simple-user" />
        </header>
        <ConsultantQueueSidebar activeBucket={null} {...sidebarSummary} contactsActive />

        <section
          id="consultant-contacts-panel"
          className="consultant-contacts-panel consultant-directory-panel"
          role="tabpanel"
          aria-labelledby="consultant-contacts-title"
        >
          <header className="consultant-contacts-head">
            <div>
              <h1 id="consultant-contacts-title">직원 연락처</h1>
              {ready && <span className="consultant-contacts-total">전체 {contacts.length}명</span>}
            </div>
            <button type="button" className="consultant-contacts-refresh" aria-label="직원 연락처 새로고침" disabled={!ready} onClick={refreshContacts}>
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="M20 7v5h-5M4 17v-5h5M5.1 8a8 8 0 0 1 13.4-3L20 7M4 17l1.5 2A8 8 0 0 0 18.9 16" />
              </svg>
              새로고침
            </button>
          </header>

          <div className="consultant-contacts-content">
            {ready && contacts.length > 0 && (
              <section
                className="consultant-contacts-organization"
                aria-labelledby="consultant-contacts-organization-title"
              >
                <header className="consultant-contacts-organization__head">
                  <div>
                    <span>WATERBRIDGE DIRECTORY</span>
                    <h2 id="consultant-contacts-organization-title">조직도</h2>
                    <p>부서와 방문 서비스 지점을 선택하면 해당 연락처만 바로 확인할 수 있습니다.</p>
                  </div>
                  <dl className="consultant-contacts-organization__stats">
                    <div><dt>본사 직원</dt><dd>{contacts.filter((contact) => contact.kind === "CONSULTANT").length}명</dd></div>
                    <div><dt>방문기사</dt><dd>{contacts.filter((contact) => contact.kind === "TECHNICIAN").length}명</dd></div>
                    <div><dt>부서</dt><dd>{consultantGroups.length}개</dd></div>
                    <div><dt>서비스 지점</dt><dd>{technicianGroups.length}개</dd></div>
                  </dl>
                </header>

                <div className="consultant-contacts-organization__root">
                  <button
                    type="button"
                    aria-label="전체 조직 연락처 보기"
                    aria-pressed={kindFilter === "ALL" && departmentFilter === "ALL" && !searchQuery}
                    onClick={resetFilters}
                  >
                    <span>WATERBRIDGE</span>
                    <strong>고객지원 통합 조직</strong>
                    <small>총 {contacts.length}명 · {organizationGroups.length}개 조직</small>
                  </button>
                </div>

                <div className="consultant-contacts-organization__divisions">
                  {[
                    { id: "office", eyebrow: "본사 조직", title: "고객 지원 부서", groups: consultantGroups },
                    { id: "field", eyebrow: "현장 조직", title: "방문 서비스 네트워크", groups: technicianGroups },
                  ].map((division) => (
                    <section key={division.id} className="consultant-contacts-division" aria-labelledby={`consultant-contacts-${division.id}-title`}>
                      <header>
                        <span>{division.eyebrow}</span>
                        <h3 id={`consultant-contacts-${division.id}-title`}>{division.title}</h3>
                        <small>{division.groups.length}개 조직</small>
                      </header>
                      <div className="consultant-contacts-division__groups">
                        {division.groups.map((group) => (
                          <button
                            key={group.id}
                            type="button"
                            aria-label={`${group.department} 연락처 보기`}
                            aria-pressed={kindFilter === group.kind && departmentFilter === group.department}
                            onClick={() => selectOrganizationGroup(group)}
                          >
                            <span>{group.kind === "CONSULTANT" ? "DEPARTMENT" : "SERVICE BRANCH"}</span>
                            <strong>{group.department || "미등록 조직"}</strong>
                            <small>{group.contacts.length}명 · {group.roleSummary}</small>
                            <em aria-hidden="true">›</em>
                          </button>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              </section>
            )}

            <div className="consultant-contacts-toolbar">
              <div className="consultant-contacts-filter-head">
                <div className="consultant-contacts-kinds" role="group" aria-label="연락처 구분">
                {CONTACT_KIND_FILTERS.map((filter) => (
                  <button
                    key={filter.value}
                    type="button"
                    aria-pressed={kindFilter === filter.value}
                    disabled={!ready}
                    onClick={() => {
                      setKindFilter(filter.value);
                      setDepartmentFilter("ALL");
                    }}
                  >
                    {filter.label}
                    {ready && <span>{filter.value === "ALL" ? contacts.length :
                      contacts.filter((contact) => contact.kind === filter.value).length}</span>}
                  </button>
                ))}
                </div>
                <button type="button" className="consultant-contacts-reset" disabled={!ready || !hasFilters} onClick={resetFilters}>필터 초기화</button>
              </div>

            <div className="consultant-contacts-filters">
              <form
                className="consultant-contacts-search"
                role="search"
                aria-label="직원 연락처 검색"
                onSubmit={(event) => {
                  event.preventDefault();
                  setSearchQuery(normalizeContactSearch(searchDraft));
                }}
              >
                <label htmlFor="consultant-contact-search">검색</label>
                <div>
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <circle cx="10.5" cy="10.5" r="6.25" />
                    <path d="m15.25 15.25 4.5 4.5" />
                  </svg>
                  <input
                    id="consultant-contact-search"
                    type="search"
                    aria-label="직원 이름, 부서, 연락처 검색"
                    placeholder="이름, 부서·지점, 연락처, 이메일 검색"
                    value={searchDraft}
                    disabled={!ready}
                    onChange={(event) => setSearchDraft(event.target.value)}
                  />
                  <button type="submit" disabled={!ready}>검색</button>
                </div>
              </form>
              <div className="consultant-contacts-department">
                <label htmlFor="consultant-contact-department">부서·지점</label>
                <FormSelect
                  id="consultant-contact-department"
                  aria-label="부서·지점 선택"
                  value={departmentFilter}
                  disabled={!ready}
                  onChange={setDepartmentFilter}
                  options={[
                    { value: "ALL", label: "전체 부서·지점" },
                    ...departments.map((department) => ({ value: department, label: department })),
                  ]}
                />
              </div>
            </div>
            </div>

            {loadState === "loading" ? (
              <LoadingState title="직원 연락처를 불러오고 있습니다." />
            ) : loadState === "unauthorized" ? (
              <ForbiddenState
                title="로그인이 만료되어 직원 연락처를 볼 수 없습니다."
                description="다시 로그인한 뒤 연락처를 확인해 주세요."
                actionLabel="로그인 화면으로"
                onAction={() => navigate(ROUTE_PATHS.login)}
              />
            ) : loadState === "forbidden" ? (
              <ForbiddenState
                title="직원 연락처를 볼 권한이 없습니다."
                description="상담사 계정과 활성 상태를 확인해 주세요."
              />
            ) : loadState === "error" ? (
              <ErrorState
                title="직원 연락처를 불러오지 못했습니다."
                description="네트워크 연결을 확인한 뒤 다시 시도해 주세요."
                onRetry={refreshContacts}
              />
            ) : visibleContacts.length === 0 ? (
              <EmptyState
                title={contacts.length === 0 ? "등록된 직원 연락처가 없습니다." : "조건에 맞는 연락처가 없습니다."}
                description={contacts.length === 0 ? "연락처가 등록되면 이곳에 표시됩니다." : "검색어나 부서·지점 필터를 확인해 주세요."}
                actionLabel={contacts.length > 0 ? "전체 연락처로 돌아가기" : undefined}
                onAction={contacts.length > 0 ? resetFilters : undefined}
              />
            ) : (
              <table className="consultant-contacts-table">
                <caption className="consultant-visually-hidden">전체 직원 연락처</caption>
                <thead>
                  <tr><th scope="col">이름</th><th scope="col">부서·지점</th><th scope="col">직급</th><th scope="col">연락처</th><th scope="col">이메일</th></tr>
                </thead>
                <tbody>
                  {visibleContacts.map((contact) => (
                    <tr key={contact.id}>
                      <th scope="row">
                        <div className="consultant-contact-person">
                          <span className={`consultant-contact-avatar${contact.kind === "TECHNICIAN" ? " consultant-contact-avatar--technician" : ""}`} aria-hidden="true">{contact.name.trim().slice(0, 1) || "·"}</span>
                          <span>
                            <strong>{contact.name || "이름 미등록"}</strong>
                            <small>{contact.kind === "TECHNICIAN" ? "방문기사" : "직원"}</small>
                          </span>
                        </div>
                      </th>
                      <td><span className="consultant-contact-cell-label" aria-hidden="true">부서·지점</span>{contact.department || "미등록"}</td>
                      <td><span className="consultant-contact-cell-label" aria-hidden="true">직급</span>{contact.position || "미등록"}</td>
                      <td><span className="consultant-contact-cell-label" aria-hidden="true">내선·전화</span><ContactValue name={contact.name} label="연락처" value={contact.phone} href={`tel:${contact.phone.replace(/[^+\d]/g, "")}`} onCopy={copyContact} /></td>
                      <td><span className="consultant-contact-cell-label" aria-hidden="true">이메일</span><ContactValue name={contact.name} label="이메일" value={contact.email} href={`mailto:${contact.email}`} onCopy={copyContact} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {ready && <footer className="consultant-contacts-summary">
            <span aria-live="polite">총 {visibleContacts.length}명{hasFilters && <small> / 전체 {contacts.length}명</small>}</span>
            <span className="consultant-contacts-copy-feedback" role="status" aria-live="polite">{copyFeedback}</span>
          </footer>}
        </section>
      </main>
    </div>
  );
}

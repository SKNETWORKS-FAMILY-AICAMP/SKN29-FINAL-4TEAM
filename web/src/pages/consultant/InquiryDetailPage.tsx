import { useNavigate, useParams } from "react-router-dom";

import { ROUTE_PATHS } from "../../app/router/routePaths";

export default function InquiryDetailPage() {
  const navigate = useNavigate();
  const { inquiryId } = useParams<{ inquiryId: string }>();

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "32px",
        background: "#f6f7f9",
      }}
    >
      <p
        style={{
          margin: 0,
          color: "#2563eb",
          fontWeight: 700,
        }}
      >
        CONS-02
      </p>

      <h1>문의 상세</h1>

      <section
        style={{
          padding: "24px",
          marginTop: "24px",
          border: "1px solid #e2e8f0",
          borderRadius: "12px",
          background: "#ffffff",
        }}
      >
        <p>선택한 문의 번호</p>
        <strong>{inquiryId ?? "문의 번호 없음"}</strong>
      </section>

      <button
        type="button"
        onClick={() => navigate(ROUTE_PATHS.consultantInquiryList)}
        style={{
          padding: "10px 16px",
          marginTop: "20px",
          border: "1px solid #cbd5e1",
          borderRadius: "8px",
          background: "#ffffff",
          cursor: "pointer",
          fontWeight: 700,
        }}
      >
        목록으로 돌아가기
      </button>
    </main>
  );
}

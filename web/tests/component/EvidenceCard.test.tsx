import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import EvidenceCard from "../../src/features/evidence-viewer/components/EvidenceCard";
import { mapEvidenceToCard } from "../../src/features/evidence-viewer/model/evidenceMapper";

describe("EvidenceCard", () => {
  it("공개 근거 필드와 HTTPS 공식 링크만 표시한다", () => {
    const evidence = mapEvidenceToCard({
      dataClassification: "official",
      documentTitle: "공식 사용설명서",
      documentVersion: "REV.00",
      page: 39,
      summary: "제품 사용을 중지하고 상담합니다.",
      sourceLandingUrl: "https://example.com/manual",
      verificationLabel: "검증 완료",
    });

    render(<EvidenceCard evidence={evidence} />);

    expect(screen.getByRole("heading", { name: "공식 사용설명서" })).toBeInTheDocument();
    expect(screen.getByText("근거 페이지")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "공식 출처 보기 ↗" })).toHaveAttribute(
      "href",
      "https://example.com/manual",
    );
    expect(screen.queryByText(/근거 항목|제공기관|위험도|안전 조치|금지 행동/)).not.toBeInTheDocument();
    expect(screen.queryByText(/chunk_id|검색 점수|내부 경로|직접 다운로드/)).not.toBeInTheDocument();
  });
});

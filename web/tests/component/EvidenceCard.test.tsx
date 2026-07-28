import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import EvidenceCard from "../../src/features/evidence-viewer/components/EvidenceCard";
import { mapEvidenceToCard } from "../../src/features/evidence-viewer/model/evidenceMapper";

describe("EvidenceCard", () => {
  it("공개 근거 필드와 HTTPS 공식 링크만 표시한다", () => {
    const evidence = mapEvidenceToCard({
      documentTitle: "공식 사용설명서",
      documentVersion: "REV.00",
      page: 39,
      sectionTitle: "고장이라고 생각되면",
      summary: "제품 사용을 중지하고 상담합니다.",
      riskLevel: "danger",
      safeActions: ["사용 중지"],
      prohibitedActions: ["직접 수리"],
      sourceLandingUrl: "https://example.com/manual",
      sourceDirectDownloadUrl: "http://example.com/internal.pdf",
    });

    render(<EvidenceCard evidence={evidence} />);

    expect(screen.getByRole("heading", { name: "공식 사용설명서" })).toBeInTheDocument();
    expect(screen.getByText("근거 페이지")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "공식 출처 보기 ↗" })).toHaveAttribute(
      "href",
      "https://example.com/manual",
    );
    expect(screen.queryByRole("link", { name: "설명서 PDF 열기 ↗" })).not.toBeInTheDocument();
    expect(screen.queryByText(/chunk_id|검색 점수|내부 경로/)).not.toBeInTheDocument();
  });
});

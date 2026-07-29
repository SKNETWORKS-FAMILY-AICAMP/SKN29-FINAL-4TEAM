import { describe, expect, it } from "vitest";

import danger from "../fixtures/consultation/danger.json";
import empty from "../fixtures/consultation/empty.json";
import noEvidence from "../fixtures/consultation/no-evidence.json";
import normal from "../fixtures/consultation/normal.json";
import reopened from "../fixtures/consultation/reopened.json";

describe("공식 데이터 기반 Web 계약 fixture", () => {
  it("정상·위험·재개·무근거·빈 목록 시나리오를 제공한다", () => {
    expect(normal.risk_level).toBe("general");
    expect(danger.risk_level).toBe("danger");
    expect(reopened.status).toBe("REOPENED");
    expect(noEvidence.evidence_ids).toEqual([]);
    expect(empty).toEqual([]);
  });
});

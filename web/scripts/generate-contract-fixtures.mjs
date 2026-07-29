import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const sourcePath = resolve(
  scriptDirectory,
  "../../data/synthetic/fixtures/inquiries.json",
);
const outputDirectory = resolve(
  scriptDirectory,
  "../tests/fixtures/consultation",
);
const inquiries = JSON.parse(await readFile(sourcePath, "utf8"));

function required(label, predicate) {
  const inquiry = inquiries.find(predicate);
  if (!inquiry) throw new Error(`${label} fixture 원본을 찾을 수 없습니다.`);
  return inquiry;
}

const fixtures = {
  "normal.json": required(
    "normal",
    (item) => item.risk_level === "general" && item.status !== "REOPENED",
  ),
  "danger.json": required("danger", (item) => item.risk_level === "danger"),
  "reopened.json": required("reopened", (item) => item.status === "REOPENED"),
  "no-evidence.json": required(
    "no-evidence",
    (item) => item.evidence_ids.length === 0,
  ),
  "empty.json": [],
  "error.json": {
    code: "INQUIRY-LIST-MOCK-ERROR",
    message: "공식 fixture 조회 실패 시나리오",
    details: {},
  },
};

await mkdir(outputDirectory, { recursive: true });
await Promise.all(
  Object.entries(fixtures).map(([name, value]) =>
    writeFile(
      resolve(outputDirectory, name),
      `${JSON.stringify(value, null, 2)}\n`,
      "utf8",
    ),
  ),
);

console.log(
  `공식 inquiries.json에서 ${Object.keys(fixtures).length}개 Web 계약 fixture를 생성했습니다.`,
);

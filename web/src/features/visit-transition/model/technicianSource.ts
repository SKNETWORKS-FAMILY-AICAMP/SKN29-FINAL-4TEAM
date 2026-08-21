import { ApiClientError } from "../../../common/api/apiError";

export type TechnicianSourceFailureStatus = "forbidden" | "error";

export function classifyTechnicianSourceFailure(
  caught: unknown,
): TechnicianSourceFailureStatus {
  return caught instanceof ApiClientError &&
    (caught.status === 403 || caught.kind === "FORBIDDEN")
    ? "forbidden"
    : "error";
}

"""명시적으로 확인된 Disposable DB에만 pgvector 검증 Schema를 생성한다."""

import json
import os

from ai.app.integrations.vector_store.vector_store import PgVectorStore


def main() -> None:
    dsn = os.getenv("AI_VECTOR_DSN")
    confirmation = os.getenv("AI_VECTOR_DISPOSABLE_CONFIRM")
    if not dsn:
        raise RuntimeError("AI_VECTOR_DSN이 필요합니다.")
    if confirmation != "DISPOSABLE_ONLY":
        raise RuntimeError(
            "AI_VECTOR_DISPOSABLE_CONFIRM=DISPOSABLE_ONLY 확인 없이는 DDL을 실행하지 않습니다."
        )
    PgVectorStore(dsn).initialize_schema(disposable_confirm=True)
    print(json.dumps({"status": "DISPOSABLE_VECTOR_SCHEMA_READY"}))


if __name__ == "__main__":
    main()

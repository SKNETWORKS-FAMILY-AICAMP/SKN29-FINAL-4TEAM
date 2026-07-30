"""공통코드 DB 제약에 사용하는 이식 가능한 SQL 표현식."""

from django.db import models


class IsJSONObject(models.Func):
    """JSON 값이 최상위 object인지 DB별 함수로 확인한다."""

    output_field = models.BooleanField()

    def as_postgresql(
        self,
        compiler,
        connection,
        **extra_context,
    ):
        return super().as_sql(
            compiler,
            connection,
            template=(
                "jsonb_typeof(%(expressions)s) = 'object'"
            ),
            **extra_context,
        )

    def as_sqlite(
        self,
        compiler,
        connection,
        **extra_context,
    ):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_TYPE(%(expressions)s) = 'object'",
            **extra_context,
        )

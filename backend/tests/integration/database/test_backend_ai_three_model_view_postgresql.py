"""Actual PostgreSQL regression for the verified three-model AI view."""

from __future__ import annotations

import os

import psycopg
import pytest

from config.env import build_postgres_connection_options


TARGET_DATABASE = "waterbridge_team_integration"
EXPECTED_MODEL_COUNTS = {
    "WPUJAC104DWH": 15,
    "WPUIAC425SNW": 19,
    "WPUIAC606SNW": 19,
}
EXPECTED_PRODUCT_SUPPORT = {
    "WPUJAC104DWH": (True, True),
    "WPUIAC425SNW": (True, False),
    "WPUIAC606SNW": (True, False),
}
ROLE_PASSWORD_KEYS = {
    "waterbridge_ti_runtime": "TEAM_INTEGRATION_RUNTIME_PASSWORD",
    "waterbridge_ti_ai_readonly": "TEAM_INTEGRATION_AI_PASSWORD",
}
BASE_TABLES = (
    "public.knowledge_ai_chunk_crosswalk",
    "public.knowledge_document_chunk",
    "public.knowledge_chunk_embedding",
)


pytestmark = pytest.mark.skipif(
    os.getenv("BACKEND_AI_THREE_MODEL_POSTGRES_TEST") != "1",
    reason="three-model PostgreSQL 검증을 명시적으로 요청하지 않음",
)


def connect_as(role_name: str):
    password_key = ROLE_PASSWORD_KEYS[role_name]
    password = os.getenv(password_key, "")
    assert password, f"필수 환경변수가 없습니다: {password_key}"
    return psycopg.connect(
        dbname=TARGET_DATABASE,
        user=role_name,
        password=password,
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        **build_postgres_connection_options(os.environ),
    )


def scalar(connection, query: str, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return cursor.fetchone()[0]


def has_table_privilege(connection, table: str, privilege: str) -> bool:
    return scalar(
        connection,
        "SELECT has_table_privilege(current_user, %s, %s)",
        (table, privilege),
    )


def test_three_model_crosswalk_view_and_public_scope_postgresql():
    with connect_as("waterbridge_ti_runtime") as connection:
        assert scalar(connection, "SELECT current_database()") == TARGET_DATABASE
        view_definition = scalar(
            connection,
            "SELECT pg_get_viewdef('public.backend_ai_rag_chunks_v1'::regclass, true)",
        )
        assert "is_supported_mvp" not in view_definition
        for model_code in EXPECTED_MODEL_COUNTS:
            assert model_code in view_definition
        assert scalar(
            connection,
            "SELECT COUNT(*) FROM knowledge_ai_chunk_crosswalk "
            "WHERE is_active AND is_verified "
            "AND canonical_verification_status = "
            "'TEXT_AND_VISUAL_VERIFIED'",
        ) == 53
        assert scalar(
            connection,
            "SELECT COUNT(*) "
            "FROM knowledge_ai_chunk_crosswalk_page AS page_link "
            "JOIN knowledge_ai_chunk_crosswalk AS crosswalk "
            "ON crosswalk.id = page_link.crosswalk_id "
            "WHERE crosswalk.is_active AND crosswalk.is_verified "
            "AND crosswalk.canonical_verification_status = "
            "'TEXT_AND_VISUAL_VERIFIED'",
        ) == 53
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT model_code, is_active, is_supported_mvp "
                "FROM catalog_product_model "
                "WHERE model_code = ANY(%s) ORDER BY model_code",
                (list(EXPECTED_MODEL_COUNTS),),
            )
            actual_product_support = {
                row[0]: (bool(row[1]), bool(row[2]))
                for row in cursor.fetchall()
            }
        assert actual_product_support == EXPECTED_PRODUCT_SUPPORT

    with connect_as("waterbridge_ti_ai_readonly") as connection:
        assert scalar(connection, "SHOW default_transaction_read_only") == "on"
        assert scalar(
            connection,
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')",
        ) is False
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*), COUNT(DISTINCT chunk_id), "
                "COUNT(*) FILTER (WHERE "
                "NULLIF(metadata ->> 'evidence_group_id', '') IS NOT NULL "
                "AND NULLIF(metadata ->> 'source_variant_id', '') IS NOT NULL "
                "AND NULLIF(metadata ->> 'parent_id', '') IS NOT NULL "
                "AND metadata ->> 'retrieval_role' = 'SEARCH_CANDIDATE') "
                "FROM public.backend_ai_rag_chunks_v1"
            )
            assert cursor.fetchone() == (53, 53, 53)
            cursor.execute(
                "SELECT model_code, COUNT(*) "
                "FROM public.backend_ai_rag_chunks_v1 "
                "GROUP BY model_code ORDER BY model_code"
            )
            assert dict(cursor.fetchall()) == EXPECTED_MODEL_COUNTS

        assert has_table_privilege(
            connection,
            "public.backend_ai_rag_chunks_v1",
            "SELECT",
        ) is True
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            assert has_table_privilege(
                connection,
                "public.backend_ai_rag_chunks_v1",
                privilege,
            ) is False
        for table_name in BASE_TABLES:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert has_table_privilege(
                    connection,
                    table_name,
                    privilege,
                ) is False

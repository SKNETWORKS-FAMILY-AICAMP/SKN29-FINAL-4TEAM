-- WaterCare SQLite compatibility schema
-- Artifact version: 3.0.0
-- PostgreSQL 운영 명세를 로컬 검증용 SQLite 타입으로 변환한 빈 스키마입니다.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 300;

CREATE TABLE "common_code_group" (
  "group_code" TEXT PRIMARY KEY,
  "group_name" TEXT NOT NULL,
  "description" TEXT,
  "display_order" INTEGER NOT NULL DEFAULT 0,
  "is_active" INTEGER NOT NULL DEFAULT 1,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "common_code" (
  "id" TEXT PRIMARY KEY,
  "group_code" TEXT NOT NULL REFERENCES "common_code_group"("group_code") ON DELETE RESTRICT,
  "code" TEXT NOT NULL,
  "code_name" TEXT NOT NULL,
  "description" TEXT,
  "display_order" INTEGER NOT NULL DEFAULT 0,
  "is_active" INTEGER NOT NULL DEFAULT 1,
  "metadata" TEXT NOT NULL DEFAULT '{}',
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "accounts_user" (
  "id" TEXT PRIMARY KEY,
  "username" TEXT NOT NULL UNIQUE,
  "password" TEXT NOT NULL,
  "email" TEXT,
  "full_name" TEXT NOT NULL,
  "phone" TEXT,
  "role_code" TEXT NOT NULL,
  "employee_no" TEXT,
  "last_login" TEXT,
  "is_superuser" INTEGER NOT NULL DEFAULT 0,
  "is_staff" INTEGER NOT NULL DEFAULT 0,
  "is_active" INTEGER NOT NULL DEFAULT 1,
  "date_joined" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "catalog_product_model" (
  "id" TEXT PRIMARY KEY,
  "model_code" TEXT NOT NULL UNIQUE,
  "model_name" TEXT NOT NULL,
  "generation_code" TEXT,
  "manufacturer" TEXT NOT NULL DEFAULT 'SK매직',
  "launched_on" TEXT,
  "discontinued_on" TEXT,
  "features" TEXT NOT NULL DEFAULT '{}',
  "is_supported_mvp" INTEGER NOT NULL DEFAULT 0,
  "is_active" INTEGER NOT NULL DEFAULT 1,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "customers_customer_profile" (
  "id" TEXT PRIMARY KEY,
  "user_id" TEXT NOT NULL UNIQUE REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "customer_no" TEXT NOT NULL UNIQUE,
  "customer_name" TEXT NOT NULL,
  "phone" TEXT,
  "postal_code" TEXT,
  "address_line1" TEXT,
  "address_line2" TEXT,
  "consent_version" TEXT,
  "consented_at" TEXT,
  "is_synthetic" INTEGER NOT NULL DEFAULT 1,
  "deleted_at" TEXT,
  "deleted_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "subscriptions_customer_subscription" (
  "id" TEXT PRIMARY KEY,
  "contract_no" TEXT NOT NULL UNIQUE,
  "customer_id" TEXT NOT NULL REFERENCES "customers_customer_profile"("id") ON DELETE RESTRICT,
  "product_model_id" TEXT NOT NULL REFERENCES "catalog_product_model"("id") ON DELETE RESTRICT,
  "serial_no" TEXT NOT NULL,
  "management_type_code" TEXT NOT NULL DEFAULT 'VISIT_CARE',
  "status_code" TEXT NOT NULL DEFAULT 'ACTIVE',
  "started_on" TEXT NOT NULL,
  "ended_on" TEXT,
  "installed_at" TEXT,
  "installation_address" TEXT,
  "next_care_on" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "subscriptions_care_record" (
  "id" TEXT PRIMARY KEY,
  "subscription_id" TEXT NOT NULL REFERENCES "subscriptions_customer_subscription"("id") ON DELETE RESTRICT,
  "visit_result_id" TEXT REFERENCES "field_service_visit_result"("id") ON DELETE RESTRICT,
  "care_type_code" TEXT NOT NULL,
  "status_code" TEXT NOT NULL DEFAULT 'SCHEDULED',
  "scheduled_on" TEXT NOT NULL,
  "completed_at" TEXT,
  "cancelled_at" TEXT,
  "cancellation_reason" TEXT,
  "summary" TEXT,
  "performed_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "source_code" TEXT NOT NULL DEFAULT 'SYSTEM',
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_inquiry" (
  "id" TEXT PRIMARY KEY,
  "inquiry_no" TEXT NOT NULL UNIQUE,
  "subscription_id" TEXT NOT NULL REFERENCES "subscriptions_customer_subscription"("id") ON DELETE RESTRICT,
  "initiated_by_id" TEXT NOT NULL REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "assigned_counselor_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "current_owner_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "current_owner_role_code" TEXT,
  "channel_code" TEXT NOT NULL DEFAULT 'WEB',
  "raw_text" TEXT NOT NULL,
  "status_code" TEXT NOT NULL DEFAULT 'DRAFT',
  "state_version" INTEGER NOT NULL DEFAULT 1,
  "priority_code" TEXT NOT NULL DEFAULT 'NORMAL',
  "risk_level_code" TEXT NOT NULL DEFAULT 'NORMAL',
  "usage_guidance_code" TEXT,
  "usage_guidance_message" TEXT,
  "restricted_functions" TEXT NOT NULL DEFAULT '[]',
  "next_action" TEXT NOT NULL DEFAULT '{}',
  "requires_consultation" INTEGER,
  "customer_action_required" INTEGER NOT NULL DEFAULT 1,
  "completion_route_code" TEXT,
  "required_finalizer_role_code" TEXT,
  "required_finalizer_user_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "opened_at" TEXT,
  "closed_at" TEXT,
  "deleted_at" TEXT,
  "deleted_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_inquiry_symptom" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL UNIQUE REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "symptom_type_code" TEXT NOT NULL,
  "occurrence_condition" TEXT,
  "accompanying_symptoms" TEXT,
  "duration_text" TEXT,
  "location_text" TEXT,
  "structured_payload" TEXT NOT NULL,
  "schema_version" TEXT NOT NULL DEFAULT 'v1',
  "source_ai_run_id" TEXT REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "is_customer_confirmed" INTEGER NOT NULL DEFAULT 0,
  "confirmed_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "confirmed_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_inquiry_qa" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "sequence_no" INTEGER NOT NULL,
  "question_code" TEXT,
  "question_text" TEXT NOT NULL,
  "answer_type_code" TEXT NOT NULL DEFAULT 'FREE_TEXT',
  "answer_text" TEXT,
  "answer_payload" TEXT,
  "asked_by_type_code" TEXT NOT NULL DEFAULT 'RULE',
  "source_ai_run_id" TEXT REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "answered_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "answered_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_symptom_assessment" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "assessment_version" INTEGER NOT NULL DEFAULT 1,
  "ruleset_version" TEXT NOT NULL,
  "risk_level_code" TEXT NOT NULL,
  "priority_code" TEXT NOT NULL,
  "usage_guidance_code" TEXT NOT NULL,
  "requires_counseling" INTEGER NOT NULL DEFAULT 0,
  "reason" TEXT NOT NULL,
  "rule_result" TEXT NOT NULL DEFAULT '{}',
  "assessed_by_type_code" TEXT NOT NULL DEFAULT 'RULE',
  "ai_run_id" TEXT REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_guidance" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "guidance_version" INTEGER NOT NULL DEFAULT 1,
  "review_status_code" TEXT NOT NULL DEFAULT 'PENDING',
  "title" TEXT NOT NULL,
  "summary_text" TEXT NOT NULL,
  "safety_notice" TEXT,
  "evidence_sufficiency_code" TEXT NOT NULL,
  "requires_counseling" INTEGER NOT NULL DEFAULT 0,
  "generated_by_ai_run_id" TEXT REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "reviewed_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "reviewed_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_guidance_item" (
  "id" TEXT PRIMARY KEY,
  "guidance_id" TEXT NOT NULL REFERENCES "support_guidance"("id") ON DELETE RESTRICT,
  "step_no" INTEGER NOT NULL,
  "action_type_code" TEXT NOT NULL,
  "instruction_text" TEXT NOT NULL,
  "caution_text" TEXT,
  "requires_confirmation" INTEGER NOT NULL DEFAULT 1,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_customer_action_result" (
  "id" TEXT PRIMARY KEY,
  "guidance_item_id" TEXT NOT NULL REFERENCES "support_guidance_item"("id") ON DELETE RESTRICT,
  "attempt_no" INTEGER NOT NULL DEFAULT 1,
  "result_code" TEXT NOT NULL,
  "result_text" TEXT,
  "performed_at" TEXT,
  "customer_comment" TEXT,
  "submitted_by_id" TEXT NOT NULL REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "idempotency_key" TEXT NOT NULL UNIQUE,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_consultation" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "counselor_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "assigned_at" TEXT,
  "status_code" TEXT NOT NULL DEFAULT 'WAITING',
  "state_version" INTEGER NOT NULL DEFAULT 1,
  "started_at" TEXT,
  "ended_at" TEXT,
  "customer_summary" TEXT NOT NULL,
  "counselor_notes" TEXT,
  "disposition_code" TEXT,
  "visit_required" INTEGER NOT NULL DEFAULT 0,
  "ai_summary_draft" TEXT,
  "final_summary" TEXT,
  "next_action" TEXT,
  "cancellation_reason" TEXT,
  "deleted_at" TEXT,
  "deleted_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_handoff_report" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "consultation_id" TEXT NOT NULL REFERENCES "support_consultation"("id") ON DELETE RESTRICT,
  "report_version" INTEGER NOT NULL DEFAULT 1,
  "report_status_code" TEXT NOT NULL DEFAULT 'DRAFT',
  "product_summary" TEXT NOT NULL,
  "symptom_summary" TEXT NOT NULL,
  "action_summary" TEXT NOT NULL,
  "risk_summary" TEXT NOT NULL,
  "evidence_summary" TEXT,
  "priority_check_items" TEXT NOT NULL DEFAULT '[]',
  "ai_draft" TEXT,
  "counselor_final" TEXT,
  "generated_by_ai_run_id" TEXT REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "confirmed_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "confirmed_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "field_service_visit" (
  "id" TEXT PRIMARY KEY,
  "visit_no" TEXT NOT NULL UNIQUE,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "handoff_report_id" TEXT NOT NULL REFERENCES "support_handoff_report"("id") ON DELETE RESTRICT,
  "technician_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "visit_status_code" TEXT NOT NULL DEFAULT 'ASSIGNING',
  "state_version" INTEGER NOT NULL DEFAULT 1,
  "scheduled_start_at" TEXT,
  "scheduled_end_at" TEXT,
  "address_snapshot" TEXT NOT NULL,
  "contact_snapshot" TEXT,
  "assigned_at" TEXT,
  "started_at" TEXT,
  "completed_at" TEXT,
  "cancelled_at" TEXT,
  "cancellation_reason" TEXT,
  "deleted_at" TEXT,
  "deleted_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "field_service_visit_result" (
  "id" TEXT PRIMARY KEY,
  "visit_id" TEXT NOT NULL UNIQUE REFERENCES "field_service_visit"("id") ON DELETE RESTRICT,
  "cause_category_code" TEXT,
  "inspection_summary" TEXT NOT NULL,
  "action_summary" TEXT NOT NULL,
  "parts_used_text" TEXT,
  "customer_guidance" TEXT,
  "resolved_on_site" INTEGER NOT NULL DEFAULT 0,
  "revisit_required" INTEGER NOT NULL DEFAULT 0,
  "revisit_reason" TEXT,
  "technician_note" TEXT,
  "submitted_by_id" TEXT NOT NULL REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "idempotency_key" TEXT NOT NULL UNIQUE,
  "completed_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "next_care_on" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_followup_confirmation" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "guidance_id" TEXT REFERENCES "support_guidance"("id") ON DELETE RESTRICT,
  "consultation_id" TEXT REFERENCES "support_consultation"("id") ON DELETE RESTRICT,
  "visit_id" TEXT REFERENCES "field_service_visit"("id") ON DELETE RESTRICT,
  "channel_code" TEXT NOT NULL DEFAULT 'WEB',
  "requested_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "responded_at" TEXT,
  "resolution_status_code" TEXT NOT NULL DEFAULT 'PENDING',
  "state_version" INTEGER NOT NULL DEFAULT 1,
  "customer_response" TEXT,
  "response_recorded_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "response_idempotency_key" TEXT UNIQUE,
  "unresolved_reason" TEXT,
  "next_action" TEXT,
  "confirmed_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "confirmed_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_inquiry_status_history" (
  "id" TEXT PRIMARY KEY,
  "questionnaire_session_id" TEXT REFERENCES "support_questionnaire_session"("id") ON DELETE RESTRICT,
  "inquiry_id" TEXT REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "consultation_id" TEXT REFERENCES "support_consultation"("id") ON DELETE RESTRICT,
  "visit_id" TEXT REFERENCES "field_service_visit"("id") ON DELETE RESTRICT,
  "target_type_code" TEXT NOT NULL,
  "event_code" TEXT NOT NULL,
  "from_status_code" TEXT,
  "to_status_code" TEXT NOT NULL,
  "state_version" INTEGER NOT NULL,
  "change_reason" TEXT,
  "changed_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "changed_by_type_code" TEXT NOT NULL DEFAULT 'USER',
  "correlation_id" TEXT NOT NULL,
  "idempotency_key" TEXT NOT NULL UNIQUE,
  "changed_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_ingestion_batch" (
  "id" TEXT PRIMARY KEY,
  "batch_no" TEXT NOT NULL UNIQUE,
  "dataset_scope_code" TEXT NOT NULL DEFAULT 'MVP',
  "source_type_code" TEXT NOT NULL,
  "status_code" TEXT NOT NULL DEFAULT 'QUEUED',
  "idempotency_key" TEXT NOT NULL UNIQUE,
  "correlation_id" TEXT NOT NULL,
  "started_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "started_at" TEXT,
  "completed_at" TEXT,
  "total_count" INTEGER NOT NULL DEFAULT 0,
  "success_count" INTEGER NOT NULL DEFAULT 0,
  "failure_count" INTEGER NOT NULL DEFAULT 0,
  "pipeline_version" TEXT NOT NULL,
  "log_uri" TEXT,
  "error_summary" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_source_document" (
  "id" TEXT PRIMARY KEY,
  "ingestion_batch_id" TEXT NOT NULL REFERENCES "knowledge_ingestion_batch"("id") ON DELETE RESTRICT,
  "document_code" TEXT NOT NULL UNIQUE,
  "dataset_scope_code" TEXT NOT NULL DEFAULT 'MVP',
  "supersedes_document_id" TEXT REFERENCES "knowledge_source_document"("id") ON DELETE RESTRICT,
  "title" TEXT NOT NULL,
  "source_org" TEXT NOT NULL,
  "document_type_code" TEXT NOT NULL,
  "official_source_url" TEXT NOT NULL,
  "usage_terms_url" TEXT NOT NULL,
  "license_note" TEXT NOT NULL,
  "original_file_uri" TEXT NOT NULL,
  "file_name" TEXT,
  "mime_type" TEXT,
  "file_size_bytes" INTEGER,
  "sha256_hash" TEXT NOT NULL UNIQUE,
  "revision_label" TEXT,
  "published_on" TEXT,
  "collected_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "collected_by_id" TEXT NOT NULL REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "status_code" TEXT NOT NULL DEFAULT 'COLLECTED',
  "parser_version" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" TEXT,
  "deleted_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT
);

CREATE TABLE "knowledge_document_model_scope" (
  "id" TEXT PRIMARY KEY,
  "document_id" TEXT NOT NULL REFERENCES "knowledge_source_document"("id") ON DELETE RESTRICT,
  "product_model_id" TEXT NOT NULL REFERENCES "catalog_product_model"("id") ON DELETE RESTRICT,
  "applicable_from" TEXT,
  "applicable_to" TEXT,
  "applicability_note" TEXT,
  "is_verified" INTEGER NOT NULL DEFAULT 0,
  "verified_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "verified_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_document_page" (
  "id" TEXT PRIMARY KEY,
  "document_id" TEXT NOT NULL REFERENCES "knowledge_source_document"("id") ON DELETE RESTRICT,
  "page_no" INTEGER NOT NULL,
  "extracted_text" TEXT,
  "text_sha256" TEXT,
  "parse_status_code" TEXT NOT NULL DEFAULT 'PENDING',
  "review_status_code" TEXT NOT NULL DEFAULT 'PENDING',
  "is_rag_eligible" INTEGER NOT NULL DEFAULT 0,
  "exclusion_reason" TEXT,
  "reviewer_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "reviewed_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_document_chunk" (
  "id" TEXT PRIMARY KEY,
  "page_id" TEXT NOT NULL REFERENCES "knowledge_document_page"("id") ON DELETE RESTRICT,
  "chunk_no" INTEGER NOT NULL,
  "chunk_type_code" TEXT NOT NULL DEFAULT 'PARAGRAPH',
  "section_path" TEXT,
  "chunk_text" TEXT NOT NULL,
  "chunk_text_sha256" TEXT NOT NULL,
  "start_offset" INTEGER,
  "end_offset" INTEGER,
  "token_count" INTEGER,
  "tokenizer_name" TEXT,
  "tokenizer_version" TEXT,
  "symptom_tags" TEXT NOT NULL DEFAULT '[]',
  "metadata" TEXT NOT NULL DEFAULT '{}',
  "search_vector" TEXT,
  "chunking_version" TEXT NOT NULL,
  "is_active" INTEGER NOT NULL DEFAULT 1,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_chunk_embedding" (
  "id" TEXT PRIMARY KEY,
  "chunk_id" TEXT NOT NULL REFERENCES "knowledge_document_chunk"("id") ON DELETE RESTRICT,
  "embedding_model" TEXT NOT NULL,
  "embedding_model_version" TEXT NOT NULL,
  "embedding_dimension" INTEGER NOT NULL,
  "source_text_sha256" TEXT NOT NULL,
  "embedding" TEXT NOT NULL,
  "embedded_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "is_active" INTEGER NOT NULL DEFAULT 1,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_data_quality_issue" (
  "id" TEXT PRIMARY KEY,
  "ingestion_batch_id" TEXT REFERENCES "knowledge_ingestion_batch"("id") ON DELETE RESTRICT,
  "document_id" TEXT REFERENCES "knowledge_source_document"("id") ON DELETE RESTRICT,
  "page_id" TEXT REFERENCES "knowledge_document_page"("id") ON DELETE RESTRICT,
  "chunk_id" TEXT REFERENCES "knowledge_document_chunk"("id") ON DELETE RESTRICT,
  "issue_type_code" TEXT NOT NULL,
  "validation_rule_code" TEXT,
  "validator_version" TEXT,
  "severity_code" TEXT NOT NULL DEFAULT 'ERROR',
  "issue_message" TEXT NOT NULL,
  "details" TEXT NOT NULL DEFAULT '{}',
  "status_code" TEXT NOT NULL DEFAULT 'OPEN',
  "detected_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "resolved_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "resolved_at" TEXT,
  "resolution_note" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "aiops_ai_run" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "task_type_code" TEXT NOT NULL,
  "request_schema_version" TEXT NOT NULL DEFAULT 'v1',
  "response_schema_version" TEXT NOT NULL,
  "model_provider" TEXT,
  "model_name" TEXT,
  "model_config_version" TEXT NOT NULL DEFAULT 'v1',
  "model_config" TEXT NOT NULL DEFAULT '{}',
  "prompt_version" TEXT,
  "input_payload" TEXT NOT NULL DEFAULT '{}',
  "input_sha256" TEXT NOT NULL,
  "idempotency_key" TEXT NOT NULL UNIQUE,
  "raw_output_text" TEXT,
  "validated_output_payload" TEXT,
  "schema_validation_status_code" TEXT NOT NULL DEFAULT 'NOT_RUN',
  "schema_validation_errors" TEXT NOT NULL DEFAULT '[]',
  "status_code" TEXT NOT NULL DEFAULT 'QUEUED',
  "started_at" TEXT,
  "completed_at" TEXT,
  "latency_ms" INTEGER,
  "input_tokens" INTEGER,
  "output_tokens" INTEGER,
  "error_code" TEXT,
  "error_message" TEXT,
  "retry_count" INTEGER NOT NULL DEFAULT 0,
  "correlation_id" TEXT NOT NULL,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "aiops_retrieval_run" (
  "id" TEXT PRIMARY KEY,
  "ai_run_id" TEXT NOT NULL REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "query_text" TEXT NOT NULL,
  "query_sha256" TEXT NOT NULL,
  "filter_payload" TEXT NOT NULL DEFAULT '{}',
  "retrieval_config_version" TEXT NOT NULL,
  "retrieval_config" TEXT NOT NULL DEFAULT '{}',
  "embedding_model" TEXT,
  "embedding_model_version" TEXT,
  "distance_metric_code" TEXT,
  "top_k" INTEGER NOT NULL DEFAULT 10,
  "reranker_name" TEXT,
  "status_code" TEXT NOT NULL DEFAULT 'QUEUED',
  "started_at" TEXT,
  "completed_at" TEXT,
  "latency_ms" INTEGER,
  "no_evidence_reason" TEXT,
  "error_code" TEXT,
  "error_message" TEXT,
  "correlation_id" TEXT NOT NULL,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "aiops_retrieval_hit" (
  "id" TEXT PRIMARY KEY,
  "retrieval_run_id" TEXT NOT NULL REFERENCES "aiops_retrieval_run"("id") ON DELETE RESTRICT,
  "chunk_id" TEXT NOT NULL REFERENCES "knowledge_document_chunk"("id") ON DELETE RESTRICT,
  "rank_no" INTEGER NOT NULL,
  "vector_score" REAL,
  "keyword_score" REAL,
  "hybrid_score" REAL,
  "rerank_score" REAL,
  "applicability_status_code" TEXT NOT NULL DEFAULT 'PENDING',
  "applicability_reason" TEXT,
  "selected_for_answer" INTEGER NOT NULL DEFAULT 0,
  "selected_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "knowledge_evidence_link" (
  "id" TEXT PRIMARY KEY,
  "inquiry_id" TEXT NOT NULL REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "guidance_id" TEXT REFERENCES "support_guidance"("id") ON DELETE RESTRICT,
  "consultation_id" TEXT REFERENCES "support_consultation"("id") ON DELETE RESTRICT,
  "handoff_report_id" TEXT REFERENCES "support_handoff_report"("id") ON DELETE RESTRICT,
  "ai_run_id" TEXT REFERENCES "aiops_ai_run"("id") ON DELETE RESTRICT,
  "chunk_id" TEXT NOT NULL REFERENCES "knowledge_document_chunk"("id") ON DELETE RESTRICT,
  "retrieval_hit_id" TEXT REFERENCES "aiops_retrieval_hit"("id") ON DELETE RESTRICT,
  "retrieval_run_id" TEXT REFERENCES "aiops_retrieval_run"("id") ON DELETE RESTRICT,
  "selection_origin_code" TEXT NOT NULL DEFAULT 'AUTO_RETRIEVAL',
  "evidence_role_code" TEXT NOT NULL DEFAULT 'SUPPORTING',
  "display_order" INTEGER NOT NULL DEFAULT 1,
  "citation_label" TEXT NOT NULL,
  "document_code_snapshot" TEXT NOT NULL,
  "document_title_snapshot" TEXT NOT NULL,
  "source_org_snapshot" TEXT NOT NULL,
  "revision_label_snapshot" TEXT,
  "official_source_url_snapshot" TEXT NOT NULL,
  "document_sha256_snapshot" TEXT NOT NULL,
  "evidence_summary" TEXT NOT NULL,
  "cited_text_snapshot" TEXT NOT NULL,
  "page_no_snapshot" INTEGER NOT NULL,
  "section_snapshot" TEXT,
  "product_model_codes_snapshot" TEXT NOT NULL,
  "is_verified" INTEGER NOT NULL DEFAULT 0,
  "verified_by_id" TEXT REFERENCES "accounts_user"("id") ON DELETE RESTRICT,
  "verified_at" TEXT,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "support_questionnaire_session" (
  "id" TEXT PRIMARY KEY,
  "session_no" TEXT NOT NULL UNIQUE,
  "subscription_id" TEXT NOT NULL REFERENCES "subscriptions_customer_subscription"("id") ON DELETE RESTRICT,
  "inquiry_id" TEXT UNIQUE REFERENCES "support_inquiry"("id") ON DELETE RESTRICT,
  "questionnaire_type_code" TEXT NOT NULL DEFAULT 'CARE_PRECHECK',
  "status_code" TEXT NOT NULL DEFAULT 'UNANSWERED',
  "questionnaire_version" TEXT NOT NULL,
  "answers_payload" TEXT NOT NULL DEFAULT '{}',
  "state_version" INTEGER NOT NULL DEFAULT 1,
  "started_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "submitted_at" TEXT,
  "linked_at" TEXT,
  "creation_idempotency_key" TEXT NOT NULL UNIQUE,
  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

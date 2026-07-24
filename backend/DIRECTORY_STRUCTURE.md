# Backend 디렉토리 구조

```text
├─ .dockerignore
├─ .env.example
├─ Dockerfile
├─ README.md
├─ apps/
│  ├─ accounts/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ customer_profile.py
│  │  │  ├─ user.py
│  │  ├─ permissions.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ account_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ account_service.py
│  │  │  ├─ authentication_service.py
│  ├─ audit/
│  │  ├─ __init__.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ ai_execution_log.py
│  │  │  ├─ audit_event.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ audit_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ audit_service.py
│  ├─ care/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ care_history.py
│  │  │  ├─ care_schedule.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ care_history_repository.py
│  │  │  ├─ care_schedule_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ care_history_service.py
│  │  │  ├─ care_schedule_service.py
│  ├─ consultations/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ consultation.py
│  │  │  ├─ consultation_summary.py
│  │  ├─ permissions.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ consultation_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ consultation_service.py
│  │  │  ├─ consultation_summary_service.py
│  ├─ evidence/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ document_chunk.py
│  │  │  ├─ evidence_registry.py
│  │  │  ├─ source_document.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ document_repository.py
│  │  │  ├─ evidence_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ evidence_card_service.py
│  │  │  ├─ evidence_validation_service.py
│  │  │  ├─ source_link_service.py
│  ├─ inquiries/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers/
│  │  │  │  ├─ __init__.py
│  │  │  │  ├─ action_result.py
│  │  │  │  ├─ create_inquiry.py
│  │  │  │  ├─ inquiry_response.py
│  │  │  │  ├─ resolution_feedback.py
│  │  │  │  ├─ symptom_submission.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ customer_action_result.py
│  │  │  ├─ followup_answer.py
│  │  │  ├─ inquiry.py
│  │  │  ├─ symptom_entry.py
│  │  ├─ permissions.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ inquiry_history_repository.py
│  │  │  ├─ inquiry_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ inquiry_ai_service.py
│  │  │  ├─ inquiry_service.py
│  │  │  ├─ inquiry_transition_service.py
│  │  │  ├─ resolution_service.py
│  ├─ operations/
│  │  ├─ __init__.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ permissions.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ operations_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ operations_service.py
│  ├─ products/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ product.py
│  │  │  ├─ product_model_registry.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ model_registry_repository.py
│  │  │  ├─ product_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ product_service.py
│  │  │  ├─ product_validation_service.py
│  ├─ questionnaires/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ questionnaire_answer.py
│  │  │  ├─ questionnaire_session.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ questionnaire_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ inquiry_link_service.py
│  │  │  ├─ questionnaire_service.py
│  ├─ subscriptions/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ subscription.py
│  │  ├─ permissions.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ subscription_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ subscription_service.py
│  ├─ visits/
│  │  ├─ __init__.py
│  │  ├─ admin.py
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ serializers.py
│  │  │  ├─ urls.py
│  │  │  ├─ views.py
│  │  ├─ apps.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ technician_report.py
│  │  │  ├─ visit.py
│  │  │  ├─ visit_result.py
│  │  ├─ permissions.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ visit_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ technician_report_service.py
│  │  │  ├─ visit_completion_service.py
│  │  │  ├─ visit_service.py
│  │  │  ├─ visit_transition_service.py
│  ├─ workflow/
│  │  ├─ __init__.py
│  │  ├─ apps.py
│  │  ├─ contracts/
│  │  │  ├─ __init__.py
│  │  │  ├─ contract_validator.py
│  │  │  ├─ state_machine_loader.py
│  │  ├─ domain/
│  │  │  ├─ __init__.py
│  │  │  ├─ event.py
│  │  │  ├─ state.py
│  │  │  ├─ transition.py
│  │  │  ├─ workflow_snapshot.py
│  │  ├─ engine/
│  │  │  ├─ __init__.py
│  │  │  ├─ allowed_action_resolver.py
│  │  │  ├─ guard_evaluator.py
│  │  │  ├─ state_machine.py
│  │  ├─ migrations/
│  │  │  ├─ __init__.py
│  │  ├─ models/
│  │  │  ├─ __init__.py
│  │  │  ├─ idempotency_record.py
│  │  │  ├─ transition_history.py
│  │  ├─ repositories/
│  │  │  ├─ __init__.py
│  │  │  ├─ workflow_repository.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ idempotency_service.py
│  │  │  ├─ transition_history_service.py
├─ common/
│  ├─ __init__.py
│  ├─ api/
│  │  ├─ __init__.py
│  │  ├─ metadata.py
│  │  ├─ pagination.py
│  │  ├─ response.py
│  ├─ authentication/
│  │  ├─ __init__.py
│  │  ├─ claims.py
│  │  ├─ jwt_authentication.py
│  ├─ contracts/
│  │  ├─ __init__.py
│  │  ├─ loader.py
│  │  ├─ paths.py
│  ├─ exceptions/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  ├─ business.py
│  │  ├─ error_codes.py
│  │  ├─ handler.py
│  ├─ logging/
│  │  ├─ __init__.py
│  │  ├─ filters.py
│  │  ├─ formatter.py
│  ├─ middleware/
│  │  ├─ __init__.py
│  │  ├─ correlation_id.py
│  │  ├─ request_context.py
│  │  ├─ request_logging.py
│  ├─ models/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  ├─ soft_delete.py
│  │  ├─ versioned.py
│  ├─ utils/
│  │  ├─ __init__.py
│  │  ├─ enum.py
│  │  ├─ masking.py
│  ├─ validators/
│  │  ├─ __init__.py
│  │  ├─ datetime.py
│  │  ├─ identifiers.py
├─ config/
│  ├─ __init__.py
│  ├─ api_urls.py
│  ├─ asgi.py
│  ├─ settings/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  ├─ local.py
│  │  ├─ production.py
│  │  ├─ test.py
│  ├─ urls.py
│  ├─ wsgi.py
├─ integrations/
│  ├─ __init__.py
│  ├─ ai/
│  │  ├─ __init__.py
│  │  ├─ client.py
│  │  ├─ exceptions.py
│  │  ├─ request_mapper.py
│  │  ├─ response_mapper.py
│  │  ├─ retry_policy.py
│  │  ├─ schema_validator.py
│  ├─ object_storage/
│  │  ├─ __init__.py
│  │  ├─ client.py
│  │  ├─ exceptions.py
├─ manage.py
├─ pyproject.toml
├─ requirements/
│  ├─ base.txt
│  ├─ local.txt
│  ├─ production.txt
├─ tests/
│  ├─ __init__.py
│  ├─ api/
│  │  ├─ .gitkeep
│  ├─ conftest.py
│  ├─ factories/
│  │  ├─ .gitkeep
│  ├─ fixtures/
│  │  ├─ .gitkeep
│  ├─ integration/
│  │  ├─ .gitkeep
│  ├─ migrations/
│  │  ├─ .gitkeep
│  ├─ permissions/
│  │  ├─ .gitkeep
│  ├─ unit/
│  │  ├─ accounts/
│  │  │  ├─ .gitkeep
│  │  ├─ care/
│  │  │  ├─ .gitkeep
│  │  ├─ consultations/
│  │  │  ├─ .gitkeep
│  │  ├─ evidence/
│  │  │  ├─ .gitkeep
│  │  ├─ inquiries/
│  │  │  ├─ .gitkeep
│  │  ├─ products/
│  │  │  ├─ .gitkeep
│  │  ├─ questionnaires/
│  │  │  ├─ .gitkeep
│  │  ├─ visits/
│  │  │  ├─ .gitkeep
│  │  ├─ workflow/
│  │  │  ├─ .gitkeep
```

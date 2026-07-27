import uuid
from django.conf import settings
from django.db import models

class Product(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    product_code = models.CharField(max_length=50, default='WPUJAC104DWH')
    manual_model = models.CharField(max_length=50, default='WPU-JAC104D')
    nickname = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Inquiry(models.Model):
    class State(models.TextChoices):
        DRAFT='DRAFT','작성 중'
        QUESTIONNAIRE_IN_PROGRESS='QUESTIONNAIRE_IN_PROGRESS','문진 진행 중'
        AI_GUIDANCE='AI_GUIDANCE','AI 안내'
        CONSULTATION_REQUIRED='CONSULTATION_REQUIRED','상담 필요'
        CONSULTATION_IN_PROGRESS='CONSULTATION_IN_PROGRESS','상담 중'
        VISIT_REVIEW_PENDING='VISIT_REVIEW_PENDING','방문 검토'
        VISIT_SCHEDULING='VISIT_SCHEDULING','방문 조율'
        VISIT_SCHEDULED='VISIT_SCHEDULED','방문 예정'
        COMPLETION_PENDING='COMPLETION_PENDING','완료 확인 대기'
        REVISIT_REQUIRED='REVISIT_REQUIRED','추가 방문 필요'
        REOPENED='REOPENED','문의 재개'
        RESOLVED='RESOLVED','해결'
        CANCELLED='CANCELLED','취소'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiries')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='inquiries')
    symptom = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    detected_text = models.TextField(blank=True)
    risk_level = models.CharField(max_length=20, default='GENERAL')
    usage_guidance_status = models.CharField(max_length=30, default='NORMAL')
    state = models.CharField(max_length=40, choices=State.choices, default=State.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class InquiryImage(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='inquiries/%Y/%m/%d/')
    image_type = models.CharField(max_length=30, default='CUSTOMER_SYMPTOM')
    created_at = models.DateTimeField(auto_now_add=True)

class EvidenceCard(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='evidence_cards')
    evidence_id = models.CharField(max_length=100)
    chunk_id = models.CharField(max_length=100, blank=True)
    document_id = models.CharField(max_length=120)
    document_title = models.CharField(max_length=200)
    document_version = models.CharField(max_length=50)
    page_refs = models.JSONField(default=list)
    evidence_summary = models.TextField()
    verification_status = models.CharField(max_length=80, default='text_and_visual_verified')
    source_landing_url = models.URLField(blank=True)
    source_direct_download_url = models.URLField(blank=True)
    product_code = models.CharField(max_length=50, default='WPUJAC104DWH')
    manual_model = models.CharField(max_length=50, default='WPU-JAC104D')
    scope_role = models.CharField(max_length=50, default='mvp_primary')

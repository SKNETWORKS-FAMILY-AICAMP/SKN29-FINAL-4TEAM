import uuid
from django.conf import settings
from django.db import models
from apps.inquiries.models import Inquiry

class VisitRequest(models.Model):
    class Status(models.TextChoices):
        ASSIGNING='ASSIGNING','기사 배정 중'
        SCHEDULING='SCHEDULING','일정 조율 중'
        CONFIRMED='CONFIRMED','방문 확정'
        EN_ROUTE='EN_ROUTE','이동 중'
        IN_PROGRESS='IN_PROGRESS','방문 진행 중'
        COMPLETED='COMPLETED','방문 완료'
        FOLLOW_UP_REQUIRED='FOLLOW_UP_REQUIRED','추가 방문 필요'
        CANCELLED='CANCELLED','취소'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry = models.OneToOneField(Inquiry, on_delete=models.CASCADE, related_name='visit')
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_visits')
    customer_address = models.CharField(max_length=255)
    customer_latitude = models.DecimalField(max_digits=10, decimal_places=7)
    customer_longitude = models.DecimalField(max_digits=10, decimal_places=7)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ASSIGNING)
    departed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class TechnicianLocation(models.Model):
    visit = models.ForeignKey(VisitRequest, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_meters = models.FloatField(null=True, blank=True)
    speed_mps = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

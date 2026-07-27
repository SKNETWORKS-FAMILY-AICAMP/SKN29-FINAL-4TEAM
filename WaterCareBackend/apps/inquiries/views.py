from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import Product, Inquiry, InquiryImage, EvidenceCard
from .serializers import ProductSerializer, InquirySerializer, InquiryImageSerializer

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        return Product.objects.filter(owner=self.request.user)
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class InquiryViewSet(viewsets.ModelViewSet):
    serializer_class = InquirySerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        user = self.request.user
        if user.role in ('TECHNICIAN','COUNSELOR','ADMIN'):
            return Inquiry.objects.all().select_related('product','customer')
        return Inquiry.objects.filter(customer=user).select_related('product')
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user, state=Inquiry.State.DRAFT)

    @action(detail=True, methods=['post'])
    def submit_symptom(self, request, pk=None):
        inquiry = self.get_object()
        if inquiry.state != Inquiry.State.DRAFT:
            return Response({'detail':'DRAFT 상태에서만 제출할 수 있습니다.'}, status=409)
        inquiry.symptom = request.data.get('symptom', inquiry.symptom)
        inquiry.description = request.data.get('description', inquiry.description)
        inquiry.detected_text = request.data.get('detected_text', inquiry.detected_text)
        inquiry.state = Inquiry.State.QUESTIONNAIRE_IN_PROGRESS
        inquiry.save()
        return Response(self.get_serializer(inquiry).data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        inquiry = self.get_object()
        serializer = InquiryImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save(inquiry=inquiry)
        return Response(InquiryImageSerializer(image, context={'request':request}).data, status=201)

    @action(detail=True, methods=['post'])
    def analyze_image(self, request, pk=None):
        inquiry = self.get_object()
        text = (request.data.get('detected_text') or inquiry.detected_text or inquiry.description).lower()
        if '누수' in text or '물 고' in text or '새' in text:
            inquiry.risk_level = 'DANGER'
            inquiry.usage_guidance_status = 'TOTAL_STOP'
            inquiry.state = Inquiry.State.CONSULTATION_REQUIRED
            summary = '누수 의심 시 제품 사용을 중지하고 원수 밸브와 전원을 확인한 뒤 상담합니다.'
            page = [38]
            evidence_id = 'EVD-JAC104D-MAN-P38-LEAK'
        else:
            inquiry.risk_level = 'GENERAL'
            inquiry.usage_guidance_status = 'NORMAL'
            inquiry.state = Inquiry.State.AI_GUIDANCE
            summary = '출수량 저하 시 필터 교체 주기, 다른 수전 사용 여부와 설치 수압을 확인합니다.'
            page = [38]
            evidence_id = 'EVD-JAC104D-MAN-P38-LOW-FLOW'
        inquiry.save()
        EvidenceCard.objects.update_or_create(
            inquiry=inquiry, evidence_id=evidence_id,
            defaults={
                'chunk_id': evidence_id.replace('EVD-', 'MAN-'),
                'document_id':'MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00',
                'document_title':'WPU-JAC104D/JCC104D 사용설명서',
                'document_version':'REV.00','page_refs':page,'evidence_summary':summary,
                'product_code':inquiry.product.product_code,'manual_model':inquiry.product.manual_model,
            }
        )
        return Response({
            'suspected_symptom': inquiry.symptom or '출수량 저하',
            'risk_level': inquiry.risk_level,
            'usage_guidance_status': inquiry.usage_guidance_status,
            'requires_consultation': inquiry.state == Inquiry.State.CONSULTATION_REQUIRED,
            'inquiry': self.get_serializer(inquiry).data,
            'notice': 'MVP 샘플 분석입니다. 실제 고장 확정 진단이 아닙니다.'
        })

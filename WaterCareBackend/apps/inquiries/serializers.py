from rest_framework import serializers
from .models import Product, Inquiry, InquiryImage, EvidenceCard

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('owner',)

class InquiryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InquiryImage
        fields = ('id','image','image_type','created_at')
        read_only_fields = ('created_at',)

class EvidenceCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceCard
        fields = ('evidence_id','chunk_id','document_id','document_title','document_version','page_refs',
                  'evidence_summary','verification_status','source_landing_url','source_direct_download_url',
                  'product_code','manual_model','scope_role')

class InquirySerializer(serializers.ModelSerializer):
    images = InquiryImageSerializer(many=True, read_only=True)
    evidence_cards = EvidenceCardSerializer(many=True, read_only=True)
    class Meta:
        model = Inquiry
        fields = ('id','product','symptom','description','detected_text','risk_level','usage_guidance_status',
                  'state','images','evidence_cards','created_at','updated_at')
        read_only_fields = ('state','risk_level','usage_guidance_status','created_at','updated_at')

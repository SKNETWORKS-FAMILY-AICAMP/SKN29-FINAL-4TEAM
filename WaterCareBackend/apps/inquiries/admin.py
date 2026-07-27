from django.contrib import admin
from .models import Product, Inquiry, InquiryImage, EvidenceCard
admin.site.register([Product, Inquiry, InquiryImage, EvidenceCard])

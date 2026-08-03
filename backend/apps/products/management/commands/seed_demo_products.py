"""Wave 2 Demo 제품 모델을 반복 실행 가능하게 적재한다."""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import ProductModel


DEMO_PRODUCT_MODEL_CODE = "DEMO-PMD-001"


class Command(BaseCommand):
    help = "T-005 Wave 2 Demo ProductModel을 update_or_create합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        product, created = ProductModel.objects.update_or_create(
            model_code=DEMO_PRODUCT_MODEL_CODE,
            defaults={
                "model_name": "WaterBridge Demo 정수기",
                "generation_code": "DEMO-G1",
                "manufacturer": "SK매직",
                "launched_on": date(2026, 1, 1),
                "discontinued_on": None,
                "features": {
                    "water_modes": ["COLD", "AMBIENT"],
                    "synthetic": True,
                },
                "is_supported_mvp": True,
                "is_active": True,
            },
        )
        state = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo ProductModel ready ({state}=1, "
                f"model_code={product.model_code})"
            )
        )

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', '고객'
        TECHNICIAN = 'TECHNICIAN', '방문기사'
        COUNSELOR = 'COUNSELOR', '상담사'
        ADMIN = 'ADMIN', '운영자'
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

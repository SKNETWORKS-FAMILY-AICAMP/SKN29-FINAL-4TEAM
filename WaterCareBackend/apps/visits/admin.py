from django.contrib import admin
from .models import VisitRequest, TechnicianLocation
admin.site.register([VisitRequest, TechnicianLocation])

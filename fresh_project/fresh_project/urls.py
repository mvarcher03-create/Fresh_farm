"""
URL configuration for fresh_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.auth.models import User

# TEMPORARY ONLY — Reset admin password
def reset_admin(request):
    try:
        user = User.objects.get(username="admin")  # change if needed
        user.set_password("admin123")              # new password
        user.save()
        return HttpResponse("Admin password reset to admin123")
    except Exception as e:
        return HttpResponse(str(e))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('fresh_app.urls')),
    path('reset-admin/', reset_admin),  # <-- temporary reset URL
]

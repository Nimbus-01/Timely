#Schedulify/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),    # Map core.urls to root
    path('api/', include('users.urls')),
    path('api-auth/', include('rest_framework.urls')),   # Users app URLs
]

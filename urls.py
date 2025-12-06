# group_messaging\urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *
from django.conf import settings
from django.conf.urls.static import static

app_name = "group_messaging"

urlpatterns = [
    path('', group_list, name='group_list'),
    path('create/', group_create, name='group_create'),
    path('<int:group_id>/', group_detail, name='group_detail'),
    path('<int:group_id>/invite/', group_invite, name='group_invite'),
    path('join/<str:token>/', join_group, name='join_group'),
    path('<int:group_id>/leave/', leave_group, name='leave_group'),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)





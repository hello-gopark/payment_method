from django.urls import path
from . import views

app_name = 'parking'
urlpatterns = [
    path('', views.index, name='index'),
    path('qr_code/', views.qr_code, name='qr_code'),
    path('release_parking_spot/<int:parking_area_id>/', views.release_parking_spot, name='release_parking_spot'),
]
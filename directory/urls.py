from django.urls import path
from . import views

app_name = 'directory'

urlpatterns = [
    path('', views.directory_index, name='index'),
    path('<slug:slug>/', views.employer_detail, name='employer_detail'),
    path('<slug:slug>/go/', views.employer_redirect, name='employer_redirect'),
]

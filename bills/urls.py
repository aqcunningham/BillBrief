from django.urls import path

from . import views

app_name = "bills"

urlpatterns = [
    path("bills/<str:slug>/", views.bill_detail, name="bill_detail"),
]
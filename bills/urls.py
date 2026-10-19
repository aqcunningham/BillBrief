from django.urls import path

from . import views

app_name = "bills"

urlpatterns = [
    path("bills/<str:slug>/", views.bill_detail, name="bill_detail"),
    path("", views.home, name="home"),
    path("desk/", views.desk, name="desk"),
    path("desk/bill/<int:bill_id>/generate/", views.desk_generate, name="desk_generate"),
path("desk/brief/<int:brief_id>/", views.desk_review, name="desk_review"),
]
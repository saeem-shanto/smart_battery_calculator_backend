from django.urls import path
from .views import TariffListView
urlpatterns = [path("", TariffListView.as_view(), name="tariff-list")]

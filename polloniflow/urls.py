from django.urls import include, path

from landing.views import home

urlpatterns = [
    path("", home, name="home"),
    path("", include("painel.urls")),
]

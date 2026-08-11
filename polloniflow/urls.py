from django.templatetags.static import static
from django.urls import include, path
from django.views.generic.base import RedirectView

from landing.views import home

urlpatterns = [
    path("", home, name="home"),
    path("", include("painel.urls")),
    # Navegador antigo e robô de busca pedem /favicon.ico na raiz, ignorando a
    # marcação do <head>. Sem esta linha cada visita gerava um 404 no registro.
    path(
        "favicon.ico",
        RedirectView.as_view(url=static("landing/img/favicon.ico"), permanent=True),
    ),
]

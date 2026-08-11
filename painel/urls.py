from django.urls import path

from . import views

urlpatterns = [
    path("painel/", views.painel, name="painel"),
    path("painel/entrar/", views.entrar, name="entrar"),
    path("painel/sair/", views.sair, name="sair"),
    # Endereço curto porque é chamado a cada clique na página.
    path("evento/", views.evento, name="evento"),
]

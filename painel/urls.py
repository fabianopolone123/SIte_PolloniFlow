from django.urls import path

from . import views

urlpatterns = [
    path("painel/", views.painel, name="painel"),
    path("painel/entrar/", views.entrar, name="entrar"),
    path("painel/sair/", views.sair, name="sair"),
    path("painel/contagem/", views.contagem, name="contagem"),
    # Endereços curtos porque são chamados pela própria página, a cada clique e
    # a cada saída.
    path("evento/", views.evento, name="evento"),
    path("medida/", views.medida, name="medida"),
]

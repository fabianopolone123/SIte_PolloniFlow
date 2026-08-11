from django.shortcuts import render

from painel.coleta import aplicar_cookies, registrar_visita


def home(request):
    visita, cookies = registrar_visita(request)
    resposta = render(request, "landing/index.html", {"visita": visita})
    return aplicar_cookies(resposta, cookies, seguro=request.is_secure())

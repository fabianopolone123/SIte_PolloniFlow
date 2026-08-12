from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import relatorio
from .coleta import COOKIE_INTERNO, COOKIE_VISITANTE, DIAS_INTERNO, aplicar_cookies
from .models import EVENTOS, Clique, Visita


def _marcar_aparelho(resposta, request):
    """Marca este aparelho como sendo do dono do site."""
    return aplicar_cookies(
        resposta, [(COOKIE_INTERNO, "1", DIAS_INTERNO)], seguro=request.is_secure()
    )


def entrar(request):
    if request.user.is_authenticated:
        return redirect("painel")

    erro = ""
    if request.method == "POST":
        pessoa = authenticate(
            request,
            username=request.POST.get("usuario", "").strip(),
            password=request.POST.get("senha", ""),
        )
        if pessoa is not None and pessoa.is_active:
            login(request, pessoa)
            # Quem entra no painel num aparelho está dizendo que o aparelho é
            # dele. A partir daqui, as visitas feitas por ele não contam.
            return _marcar_aparelho(redirect("painel"), request)
        erro = "Usuário ou senha incorretos."

    return render(request, "painel/entrar.html", {"erro": erro})


@login_required
@require_POST
def contagem(request):
    """Liga e desliga a contagem das visitas feitas neste aparelho."""
    resposta = redirect("painel")
    if request.POST.get("acao") == "contar":
        resposta.delete_cookie(COOKIE_INTERNO, samesite="Lax")
        return resposta
    return _marcar_aparelho(resposta, request)


@require_POST
def sair(request):
    logout(request)
    return redirect("entrar")


@login_required
def painel(request):
    dados = relatorio.montar(relatorio.periodo_valido(request.GET.get("dias")))
    dados["aparelho_marcado"] = request.COOKIES.get(COOKIE_INTERNO) == "1"
    resposta = render(request, "painel/dashboard.html", dados)
    resposta["Cache-Control"] = "no-store"
    return resposta


@csrf_exempt
@require_POST
def evento(request):
    """Recebe o aviso de que alguém clicou num botão da página.

    Sem proteção de CSRF de propósito: o aviso é enviado por `sendBeacon`, que
    não carrega cabeçalhos, e o pedido não faz nada além de gravar uma linha de
    estatística. Em compensação, só grava se o código do botão estiver na lista
    conhecida e se a visita informada for mesmo desta pessoa, neste dia.
    """
    codigo = request.POST.get("evento", "")[:40]
    if codigo not in EVENTOS:
        return HttpResponse(status=204)

    visitante = request.COOKIES.get(COOKIE_VISITANTE, "")
    identificador = request.POST.get("visita", "")
    if not visitante or not identificador.isdigit():
        return HttpResponse(status=204)

    try:
        visita = Visita.objects.filter(
            pk=int(identificador),
            visitante=visitante,
            criado_em__gte=timezone.now() - timedelta(days=1),
        ).first()
        if visita is not None:
            Clique.objects.create(
                visita=visita,
                evento=codigo,
                canal=visita.canal,
                robo=visita.robo,
                interno=visita.interno,
            )
    except Exception:
        pass

    return HttpResponse(status=204)

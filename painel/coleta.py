"""Registro de quem visita a página inicial e de onde veio.

Tudo é anônimo: o visitante recebe um número aleatório num cookie, que só serve
para separar "quantas aberturas de página" de "quantas pessoas diferentes".
"""

import logging
import re
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit

from .models import Canal, Dispositivo, Visita

registro = logging.getLogger(__name__)

COOKIE_VISITANTE = "pf_visitante"
COOKIE_ORIGEM = "pf_origem"
DIAS_VISITANTE = 365
DIAS_ORIGEM = 90

# O domínio do próprio site: quando o referer é ele mesmo, não é "veio de fora".
DOMINIO = "fabianopolone.com.br"

# Parâmetros que as plataformas de anúncio grudam no link. A presença de
# qualquer um deles já prova que o clique veio de um anúncio pago.
CLIQUES_PAGOS = ("fbclid", "gclid", "ttclid", "msclkid", "gbraid", "wbraid", "igshid")

# Valores comuns de utm_medium em campanhas pagas.
MIDIAS_PAGAS = (
    "cpc", "ppc", "paid", "ads", "anuncio", "display", "cpm", "cpv", "retargeting",
)

# Buscadores: quem chega por aqui é tráfego orgânico de busca.
BUSCADORES = (
    "google.", "bing.", "yahoo.", "duckduckgo.", "ecosia.", "yandex.", "baidu.",
    "search.brave", "ask.com", "qwant.", "startpage.",
)

REDES = (
    "instagram.", "facebook.", "fb.com", "fb.me", "linkedin.", "lnkd.in", "t.co",
    "twitter.", "x.com", "tiktok.", "youtube.", "youtu.be", "whatsapp.", "wa.me",
    "pinterest.", "threads.", "reddit.", "telegram.", "t.me", "kwai.",
)

# utm_source usados pelas redes (o Instagram costuma mandar "ig").
FONTES_REDES = (
    "ig", "instagram", "fb", "facebook", "meta", "linkedin", "tiktok", "youtube",
    "whatsapp", "threads", "twitter", "x", "pinterest", "kwai", "telegram",
)

# Robôs de busca e de pré-visualização de link. Continuam sendo gravados, mas
# ficam de fora das contas do painel — senão o Facebook, que abre o link toda
# vez que alguém compartilha, vira "visitante".
ROBOS = (
    "bot", "crawl", "spider", "slurp", "facebookexternalhit", "preview",
    "curl", "wget", "python-requests", "httpx", "go-http", "headless",
    "monitor", "uptime", "pingdom", "lighthouse", "scanner", "semrush",
    "ahrefs", "petalbot", "applebot", "whatsapp", "telegrambot", "embed",
    "archiver", "validator", "feedfetcher", "http-client",
)

CAMPOS_ORIGEM = ("canal", "origem", "midia", "campanha", "conteudo", "termo")


def _texto(valor, tamanho):
    return (valor or "").strip()[:tamanho]


def _host_do_referer(request):
    """Domínio de onde a pessoa veio.

    Devolve vazio quando não há referer e também quando ele é o próprio site:
    navegar de uma página para outra aqui dentro não é "veio de fora", e guardar
    esse endereço só encheria o relatório de linha falsa.
    """
    referer = _texto(request.META.get("HTTP_REFERER"), 300)
    if not referer:
        return "", ""
    host = (urlsplit(referer).hostname or "").lower()
    if host == DOMINIO or host.endswith("." + DOMINIO):
        return "", ""
    return host, referer


def _dispositivo(agente):
    agente = agente.lower()
    if "ipad" in agente or "tablet" in agente or ("android" in agente and "mobile" not in agente):
        return Dispositivo.TABLET
    if any(marca in agente for marca in ("mobi", "iphone", "android", "phone", "ipod")):
        return Dispositivo.CELULAR
    return Dispositivo.COMPUTADOR


def _e_robo(agente):
    agente = agente.lower()
    if not agente:
        return True
    return any(marca in agente for marca in ROBOS)


def _endereco(request):
    # O Nginx repassa o IP real da pessoa nestes cabeçalhos; o REMOTE_ADDR aqui
    # seria sempre o próprio servidor.
    for cabecalho in ("HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"):
        valor = request.META.get(cabecalho, "")
        if valor:
            return valor.split(",")[0].strip()[:45]
    return None


def _da_requisicao(request):
    """Lê a origem desta visita. Devolve (dados, veio_marcada)."""
    parametros = request.GET
    dados = {
        "origem": _texto(parametros.get("utm_source"), 120),
        "midia": _texto(parametros.get("utm_medium"), 120),
        "campanha": _texto(parametros.get("utm_campaign"), 180),
        "conteudo": _texto(parametros.get("utm_content"), 180),
        "termo": _texto(parametros.get("utm_term"), 180),
    }
    pago = any(parametros.get(nome) for nome in CLIQUES_PAGOS)
    host, referer = _host_do_referer(request)

    midia = dados["midia"].lower()
    fonte = dados["origem"].lower()

    if pago or any(marca in midia for marca in MIDIAS_PAGAS):
        canal = Canal.ANUNCIO
    elif fonte:
        canal = Canal.SOCIAL if fonte in FONTES_REDES else Canal.REFERENCIA
    elif any(marca in host for marca in BUSCADORES):
        canal = Canal.BUSCA
    elif any(marca in host for marca in REDES):
        canal = Canal.SOCIAL
    elif host:
        canal = Canal.REFERENCIA
    else:
        # Nem marcação de campanha, nem site de origem: não dá para saber nada
        # desta visita sozinha.
        return {"canal": Canal.DIRETO, **dados}, False

    if not dados["origem"] and host:
        dados["origem"] = host[:120]
    return {"canal": canal, **dados}, True


def _do_cookie(request):
    """Recupera a origem da primeira visita desta pessoa.

    Quem chega pelo anúncio e recarrega a página não vira "direto" no relatório:
    a campanha continua valendo pelos próximos 90 dias.
    """
    guardado = request.COOKIES.get(COOKIE_ORIGEM, "")
    if not guardado or len(guardado) > 800:
        return None
    dados = {chave: valor for chave, valor in parse_qsl(guardado) if chave in CAMPOS_ORIGEM}
    if dados.get("canal") not in Canal.values:
        return None
    return {campo: dados.get(campo, "") for campo in CAMPOS_ORIGEM}


def registrar_visita(request):
    """Grava a visita. Devolve (visita, cookies) — a visita pode ser None.

    Nada aqui pode derrubar a página: se o banco falhar, o site continua no ar
    e só o relatório fica sem o registro.
    """
    visitante = request.COOKIES.get(COOKIE_VISITANTE, "")
    if not re.fullmatch(r"[0-9a-f]{32}", visitante or ""):
        visitante = uuid.uuid4().hex

    cookies = [(COOKIE_VISITANTE, visitante, DIAS_VISITANTE)]
    dados, marcada = _da_requisicao(request)
    if marcada:
        cookies.append((COOKIE_ORIGEM, urlencode(dados), DIAS_ORIGEM))
    else:
        dados = _do_cookie(request) or dados

    agente = _texto(request.META.get("HTTP_USER_AGENT"), 300)
    _, referer = _host_do_referer(request)

    try:
        visita = Visita.objects.create(
            visitante=visitante,
            canal=dados["canal"],
            origem=dados["origem"],
            midia=dados["midia"],
            campanha=dados["campanha"],
            conteudo=dados["conteudo"],
            termo=dados["termo"],
            referencia=referer,
            caminho=request.get_full_path()[:300],
            dispositivo=_dispositivo(agente),
            agente=agente,
            ip=_endereco(request),
            robo=_e_robo(agente),
        )
    except Exception:
        registro.exception("Não foi possível registrar a visita")
        visita = None

    return visita, cookies


def aplicar_cookies(resposta, cookies, seguro):
    for nome, valor, dias in cookies:
        resposta.set_cookie(
            nome,
            valor,
            max_age=dias * 24 * 60 * 60,
            secure=seguro,
            httponly=True,
            samesite="Lax",
        )
    return resposta

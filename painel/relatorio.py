"""Os números que aparecem no painel."""

from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import EVENTOS, EVENTOS_WHATSAPP, Canal, Clique, Dispositivo, Visita

# Períodos oferecidos no topo do painel.
PERIODOS = ((1, "Hoje"), (7, "7 dias"), (30, "30 dias"), (90, "90 dias"))
PERIODO_PADRAO = 30

_SO_WHATSAPP = Q(cliques__evento__in=EVENTOS_WHATSAPP)

# Rolar 90% já é ter visto a página inteira: os últimos por cento são rodapé, e
# exigir 100 marcaria como abandono quem leu tudo o que importa.
ATE_O_FIM = 90
# Quem não passou daqui viu só a primeira tela e foi embora.
SO_O_TOPO = 25
# Abaixo disso não deu tempo de ler nem o título.
SAIDA_RAPIDA = 10

FAIXAS_ROLAGEM = (
    (0, 25, "Só a primeira tela"),
    (25, 50, "Um quarto da página"),
    (50, 75, "Metade da página"),
    (75, 101, "Quase tudo ou tudo"),
)

FAIXAS_TEMPO = (
    (0, 10, "Menos de 10 segundos"),
    (10, 30, "10 a 30 segundos"),
    (30, 60, "30 segundos a 1 minuto"),
    (60, 180, "1 a 3 minutos"),
    (180, None, "Mais de 3 minutos"),
)


def periodo_valido(valor):
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return PERIODO_PADRAO
    return dias if dias in dict(PERIODOS) else PERIODO_PADRAO


def _porcentagem(parte, total):
    return round(100 * parte / total, 1) if total else 0.0


def _com_cliques(consulta, *campos):
    """Agrupa visitas por um ou mais campos, já contando os cliques no WhatsApp."""
    return consulta.values(*campos).annotate(
        visitas=Count("id", distinct=True),
        pessoas=Count("visitante", distinct=True),
        cliques=Count("cliques", filter=_SO_WHATSAPP, distinct=True),
    )


def _tempo_texto(segundos):
    """Segundos em algo que se lê de relance: 8s, 45s, 2min, 3min 20s."""
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    minutos, resto = divmod(segundos, 60)
    return f"{minutos}min" if not resto else f"{minutos}min {resto}s"


def _mediana(valores):
    """A mediana diz mais que a média aqui: uma aba esquecida aberta puxa a
    média para cima sozinha, e a mediana ignora esse tipo de exagero."""
    if not valores:
        return 0
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[meio]
    return round((ordenados[meio - 1] + ordenados[meio]) / 2)


def _distribuicao(valores, faixas):
    """Quantos valores caem em cada faixa, com a fatia de cada uma."""
    total = len(valores)
    linhas = []
    for inicio, fim, rotulo in faixas:
        quantos = sum(
            1 for valor in valores if valor >= inicio and (fim is None or valor < fim)
        )
        linhas.append(
            {
                "rotulo": rotulo,
                "total": quantos,
                "fatia": _porcentagem(quantos, total),
            }
        )
    return linhas


def _engajamento(visitas):
    """O que o clique sozinho não conta: quanto da página viram e por quanto tempo.

    Só entram as visitas medidas. Quem fechou a página antes do JavaScript rodar
    — e todas as visitas gravadas antes desta medição existir — tem rolagem e
    tempo zerados; incluí-las faria cada uma pesar na conta como um abandono
    imediato que ninguém observou. Por isso o painel mostra também a cobertura:
    de quantas visitas o número realmente saiu.
    """
    total = visitas.count()
    medidas = list(visitas.filter(medido=True).values_list("rolagem", "segundos"))
    quantidade = len(medidas)

    if not quantidade:
        return {
            "medidas": 0,
            "total": total,
            "cobertura": 0.0,
            "ate_o_fim": 0.0,
            "so_o_topo": 0.0,
            "saida_rapida": 0.0,
            "rolagem_media": 0.0,
            "tempo_mediano": 0,
            "tempo_mediano_texto": "—",
            "tempo_medio": 0,
            "tempo_medio_texto": "—",
            "faixas_rolagem": [],
            "faixas_tempo": [],
        }

    rolagens = [rolagem for rolagem, _ in medidas]
    tempos = [segundos for _, segundos in medidas]
    mediana = _mediana(tempos)
    media = round(sum(tempos) / quantidade)

    return {
        "medidas": quantidade,
        "total": total,
        "cobertura": _porcentagem(quantidade, total),
        "ate_o_fim": _porcentagem(sum(1 for r in rolagens if r >= ATE_O_FIM), quantidade),
        "so_o_topo": _porcentagem(sum(1 for r in rolagens if r < SO_O_TOPO), quantidade),
        "saida_rapida": _porcentagem(
            sum(1 for t in tempos if t < SAIDA_RAPIDA), quantidade
        ),
        "rolagem_media": round(sum(rolagens) / quantidade, 1),
        "tempo_mediano": mediana,
        "tempo_mediano_texto": _tempo_texto(mediana),
        "tempo_medio": media,
        "tempo_medio_texto": _tempo_texto(media),
        "faixas_rolagem": _distribuicao(rolagens, FAIXAS_ROLAGEM),
        "faixas_tempo": _distribuicao(tempos, FAIXAS_TEMPO),
    }


def _bloco(consulta, visitas, cliques):
    """Cartão comparativo: visitas, pessoas, cliques, conversão e engajamento."""
    engajamento = _engajamento(consulta)
    return {
        "visitas": visitas["visitas"],
        "pessoas": visitas["pessoas"],
        "cliques": cliques,
        "taxa": _porcentagem(cliques, visitas["visitas"]),
        "ate_o_fim": engajamento["ate_o_fim"],
        "tempo_mediano_texto": engajamento["tempo_mediano_texto"],
        "rolagem_media": engajamento["rolagem_media"],
        "medidas": engajamento["medidas"],
    }


def _totais(consulta):
    resultado = consulta.aggregate(
        visitas=Count("id", distinct=True),
        pessoas=Count("visitante", distinct=True),
    )
    return {"visitas": resultado["visitas"] or 0, "pessoas": resultado["pessoas"] or 0}


def _serie_diaria(visitas, cliques, primeiro_dia, ultimo_dia):
    """Uma entrada por dia do período, inclusive os dias sem nenhuma visita.

    Cada dia vira uma barra empilhada: embaixo o que veio de anúncio, em cima o
    orgânico. É a mesma leitura do resto do painel, agora ao longo do tempo.
    """
    por_dia = {
        linha["dia"]: linha
        for linha in visitas.annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(
            visitas=Count("id"),
            pessoas=Count("visitante", distinct=True),
            anuncio=Count("id", filter=Q(canal=Canal.ANUNCIO)),
        )
    }
    cliques_por_dia = {
        linha["dia"]: linha["total"]
        for linha in cliques.annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(total=Count("id"))
    }

    serie = []
    dia = primeiro_dia
    while dia <= ultimo_dia:
        linha = por_dia.get(dia, {})
        total = linha.get("visitas", 0)
        anuncio = linha.get("anuncio", 0)
        serie.append(
            {
                "dia": dia,
                "visitas": total,
                "pessoas": linha.get("pessoas", 0),
                "anuncio": anuncio,
                "organico": total - anuncio,
                "cliques": cliques_por_dia.get(dia, 0),
            }
        )
        dia += timedelta(days=1)

    teto = max([linha["visitas"] for linha in serie] + [1])
    for linha in serie:
        linha["anuncio_altura"] = round(100 * linha["anuncio"] / teto, 2)
        linha["organico_altura"] = round(100 * linha["organico"] / teto, 2)
    return serie, teto


def montar(dias):
    ultimo_dia = timezone.localdate()
    primeiro_dia = ultimo_dia - timedelta(days=dias - 1)
    inicio = timezone.make_aware(datetime.combine(primeiro_dia, time.min))

    # Robôs e as visitas do próprio dono ficam de fora de tudo o que vem
    # abaixo. Continuam gravados, só não entram na conta.
    visitas = Visita.objects.filter(criado_em__gte=inicio, robo=False, interno=False)
    cliques = Clique.objects.filter(criado_em__gte=inicio, robo=False, interno=False)
    cliques_whatsapp = cliques.filter(evento__in=EVENTOS_WHATSAPP)

    totais = _totais(visitas)
    total_cliques = cliques_whatsapp.count()

    anuncio = visitas.filter(canal=Canal.ANUNCIO)
    organico = visitas.exclude(canal=Canal.ANUNCIO)

    resumo = {
        **totais,
        "cliques": total_cliques,
        "taxa": _porcentagem(total_cliques, totais["visitas"]),
        "robos": Visita.objects.filter(criado_em__gte=inicio, robo=True).count(),
        "internos": Visita.objects.filter(
            criado_em__gte=inicio, robo=False, interno=True
        ).count(),
    }

    comparativo = {
        "anuncio": _bloco(
            anuncio,
            _totais(anuncio),
            cliques_whatsapp.filter(canal=Canal.ANUNCIO).count(),
        ),
        "organico": _bloco(
            organico,
            _totais(organico),
            cliques_whatsapp.exclude(canal=Canal.ANUNCIO).count(),
        ),
    }
    comparativo["anuncio"]["fatia"] = _porcentagem(
        comparativo["anuncio"]["visitas"], totais["visitas"]
    )
    comparativo["organico"]["fatia"] = _porcentagem(
        comparativo["organico"]["visitas"], totais["visitas"]
    )

    rotulos_canal = dict(Canal.choices)
    por_canal = [
        {
            "canal": rotulos_canal.get(linha["canal"], linha["canal"]),
            "codigo": linha["canal"],
            "visitas": linha["visitas"],
            "pessoas": linha["pessoas"],
            "cliques": linha["cliques"],
            "taxa": _porcentagem(linha["cliques"], linha["visitas"]),
            "fatia": _porcentagem(linha["visitas"], totais["visitas"]),
        }
        for linha in sorted(
            _com_cliques(visitas, "canal"), key=lambda linha: -linha["visitas"]
        )
    ]

    campanhas = [
        {
            "campanha": linha["campanha"] or "(sem nome de campanha)",
            "conteudo": linha["conteudo"] or "—",
            "origem": linha["origem"] or "—",
            "visitas": linha["visitas"],
            "pessoas": linha["pessoas"],
            "cliques": linha["cliques"],
            "taxa": _porcentagem(linha["cliques"], linha["visitas"]),
        }
        for linha in sorted(
            _com_cliques(anuncio, "campanha", "conteudo", "origem"),
            key=lambda linha: -linha["visitas"],
        )
    ]

    contagem_eventos = {
        linha["evento"]: linha
        for linha in cliques.values("evento").annotate(
            total=Count("id"), pessoas=Count("visita__visitante", distinct=True)
        )
    }
    por_evento = [
        {
            "rotulo": rotulo,
            "total": contagem_eventos.get(codigo, {}).get("total", 0),
            "pessoas": contagem_eventos.get(codigo, {}).get("pessoas", 0),
            "whatsapp": codigo in EVENTOS_WHATSAPP,
        }
        for codigo, rotulo in EVENTOS.items()
    ]
    teto_eventos = max([linha["total"] for linha in por_evento] + [1])
    for linha in por_evento:
        linha["largura"] = round(100 * linha["total"] / teto_eventos, 1)

    rotulos_dispositivo = dict(Dispositivo.choices)
    por_dispositivo = [
        {
            "dispositivo": rotulos_dispositivo.get(linha["dispositivo"], linha["dispositivo"]),
            "visitas": linha["visitas"],
            "cliques": linha["cliques"],
            "fatia": _porcentagem(linha["visitas"], totais["visitas"]),
        }
        for linha in sorted(
            _com_cliques(visitas, "dispositivo"), key=lambda linha: -linha["visitas"]
        )
    ]

    serie, teto = _serie_diaria(visitas, cliques_whatsapp, primeiro_dia, ultimo_dia)

    # O order_by é explícito porque o annotate agrupa a consulta e a ordenação
    # padrão do modelo deixa de valer.
    ultimas = list(
        visitas.annotate(cliques_whatsapp=Count("cliques", filter=_SO_WHATSAPP, distinct=True))
        .order_by("-criado_em")[:25]
    )

    return {
        "dias": dias,
        "primeiro_dia": primeiro_dia,
        "ultimo_dia": ultimo_dia,
        "resumo": resumo,
        "engajamento": _engajamento(visitas),
        "comparativo": comparativo,
        "por_canal": por_canal,
        "campanhas": campanhas,
        "por_evento": por_evento,
        "por_dispositivo": por_dispositivo,
        "serie": serie,
        "teto": teto,
        "ultimas": ultimas,
        "periodos": PERIODOS,
    }

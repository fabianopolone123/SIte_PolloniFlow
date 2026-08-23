# O relatório

[painel/relatorio.py](../painel/relatorio.py) é o arquivo que transforma as
linhas de `Visita` e `Clique` nos números da tela. Uma função pública,
`montar(dias)`, devolve o dicionário de contexto que
[dashboard.html](../painel/templates/painel/dashboard.html) renderiza.

## O filtro que vale para tudo

Antes de qualquer conta, `montar` monta duas consultas base:

```python
visitas = Visita.objects.filter(criado_em__gte=inicio, robo=False, interno=False)
cliques = Clique.objects.filter(criado_em__gte=inicio, robo=False, interno=False)
cliques_whatsapp = cliques.filter(evento__in=EVENTOS_WHATSAPP)
```

**Robô e visita interna estão fora de tudo o que aparece no painel** — exceto de
duas contagens no bloco de resumo, que existem justamente para mostrar quanto foi
descartado.

`inicio` é o começo do dia, no fuso `America/Sao_Paulo`:
`timezone.make_aware(datetime.combine(primeiro_dia, time.min))`. Isso importa:
"7 dias" significa sete dias de calendário inteiros, não as últimas 168 horas.

## O período

`PERIODOS = ((1, "Hoje"), (7, "7 dias"), (30, "30 dias"), (90, "90 dias"))`, com
padrão 30.

`periodo_valido(valor)` recebe o `?dias=` da URL e devolve **um dos quatro
valores, sempre**. Texto, número fora da lista ou parâmetro ausente caem no
padrão. É a única validação de entrada do painel, e é suficiente: nada do que vem
da URL chega ao banco sem passar por aqui.

Para acrescentar um período novo (por exemplo 180 dias), basta uma entrada nessa
tupla — o filtro no template e a validação leem dela.

## Os nove blocos

### 1. Resumo do período

| Número | Conta |
| --- | --- |
| `visitas` | `COUNT(DISTINCT id)` das visitas |
| `pessoas` | `COUNT(DISTINCT visitante)` |
| `cliques` | Total de linhas de `Clique` com evento de WhatsApp |
| `taxa` | `cliques ÷ visitas × 100`, uma casa decimal |
| `robos` | Visitas com `robo=True` no período — **não** filtra `interno` |
| `internos` | Visitas com `robo=False, interno=True` |

`robos` e `internos` são os dois únicos números do painel que olham o que foi
descartado. Servem de sanidade: se `internos` estiver zerado depois de você mexer
no site a manhã inteira, o cookie `pf_interno` daquele aparelho se perdeu.

Atenção à definição de `taxa`: o numerador conta **linhas de clique**, não
pessoas. Duas pessoas que clicam uma vez cada e uma pessoa que clica duas vezes
dão o mesmo número. Para o volume de pessoas, o bloco "Cliques nos botões" traz a
contagem de visitantes distintos por evento.

### 2. Quanto leram e quanto tempo ficaram

Vem de `_engajamento(visitas)`, e responde o que a conversão não responde: quem
saiu antes de ler e quem leu tudo e mesmo assim não chamou.

| Número | Conta |
| --- | --- |
| `ate_o_fim` | % das visitas medidas com `rolagem >= 90` |
| `so_o_topo` | % com `rolagem < 25` |
| `saida_rapida` | % com `segundos < 10` |
| `rolagem_media` | Média da rolagem, uma casa decimal |
| `tempo_mediano` / `_texto` | Mediana dos segundos, crua e formatada (`2min 30s`) |
| `tempo_medio` / `_texto` | Média, mostrada ao lado como referência |
| `faixas_rolagem` | Distribuição em 4 faixas |
| `faixas_tempo` | Distribuição em 5 faixas |
| `medidas` / `total` / `cobertura` | De quantas visitas o número saiu |

**O denominador é `medidas`, não `total`.** Só entram visitas com `medido=True`;
um período sem nenhuma medida devolve o dicionário zerado, com `"—"` nos textos de
tempo, e o template esconde o bloco (`{% if engajamento.medidas %}`).

A mecânica completa — os limites, o teto de 30 minutos, por que a mediana e por
que `medido` existe — está em [medicao-de-leitura.md](medicao-de-leitura.md).

### 3. Anúncio ou orgânico

O bloco comparativo, e a pergunta central do painel. Dois cartões:

```python
anuncio  = visitas.filter(canal=Canal.ANUNCIO)
organico = visitas.exclude(canal=Canal.ANUNCIO)
```

Cada cartão traz `visitas`, `pessoas`, `cliques`, `taxa`, `fatia` — e o próprio
engajamento: `ate_o_fim`, `tempo_mediano_texto`, `rolagem_media` e `medidas`. Foi
para isso que `_bloco` passou a receber o queryset, além dos totais já
calculados: ele chama `_engajamento` para o seu lado da comparação.

É o que permite ver, por exemplo, que o tráfego pago lê menos da página que o
espontâneo — e que a diferença de conversão entre os dois pode começar antes da
oferta.

**"Orgânico" aqui é tudo que não é anúncio pago**: busca, redes sociais, outros
sites e direto somados. É uma decisão de leitura, não um descuido: o dono do site
quer saber se o dinheiro investido rende mais que o movimento espontâneo, e a
comparação só faz sentido com esses dois lados.

### 4. Visitas por dia

`_serie_diaria(visitas, cliques_whatsapp, primeiro_dia, ultimo_dia)`.

Agrupa por `TruncDate("criado_em")` e depois **preenche os dias vazios**
percorrendo o período dia a dia num `while`. Sem isso, um dia sem visita
simplesmente não apareceria e o gráfico mentiria sobre o ritmo.

Cada dia devolve `visitas`, `pessoas`, `anuncio`, `organico` (= total − anúncio),
`cliques` e duas alturas em porcentagem:

```python
teto = max([linha["visitas"] for linha in serie] + [1])
linha["anuncio_altura"]  = round(100 * linha["anuncio"]  / teto, 2)
linha["organico_altura"] = round(100 * linha["organico"] / teto, 2)
```

O `+ [1]` no `max` evita divisão por zero num período sem nenhuma visita. As
alturas são a barra empilhada do gráfico: embaixo o anúncio, em cima o orgânico —
a mesma leitura do resto do painel, agora ao longo do tempo. O CSS só aplica
`height: {{ ... }}%`; não há biblioteca de gráfico no projeto.

### 5. De onde vieram

Uma linha por `Canal`, ordenada por visitas (decrescente), com `visitas`,
`pessoas`, `cliques`, `taxa` e `fatia`. O rótulo vem de `Canal.choices`, e
`codigo` vai junto para o template pintar o marcador de anúncio em cor diferente.

A ordenação é feita **em Python** (`sorted(..., key=lambda linha: -linha["visitas"])`),
não no banco. Com cinco canais, tanto faz.

### 6. Campanhas de anúncio

Só as visitas de `canal=anuncio`, agrupadas por
`("campanha", "conteudo", "origem")` — ou seja, **uma linha por campanha e por
criativo**. É a granularidade que responde "qual anúncio está funcionando".

Valores vazios ganham texto legível: `"(sem nome de campanha)"` para campanha e
`"—"` para conteúdo e origem. Uma linha sem nome de campanha normalmente é visita
que chegou só com `fbclid`, sem `utm` — o caso do impulsionamento de post no
Instagram.

### 7. Cliques nos botões

Este bloco olha **todos** os eventos, não só os de WhatsApp:

```python
cliques.values("evento").annotate(
    total=Count("id"),
    pessoas=Count("visita__visitante", distinct=True),
)
```

A lista final é construída percorrendo `EVENTOS` — **na ordem do dicionário** —
e não o resultado da consulta. Duas consequências boas: um botão com zero clique
aparece com zero (e não desaparece), e a ordem da tela é estável.

`whatsapp` é um booleano por linha, para o template destacar os quatro botões de
conversão. `largura` é a barra horizontal, normalizada pelo maior valor, com o
mesmo truque do `+ [1]`.

Note `pessoas=Count("visita__visitante", distinct=True)`: como a FK é `SET_NULL`,
cliques cujas visitas foram apagadas contam em `total` mas não em `pessoas`.

### 8. Aparelhos

Uma linha por `Dispositivo`, com `visitas`, `cliques` e `fatia`. Mesmo padrão do
bloco de canais.

### 9. Últimas visitas

As 25 mais recentes, cada uma com `cliques_whatsapp` anotado:

```python
visitas.annotate(cliques_whatsapp=Count("cliques", filter=_SO_WHATSAPP, distinct=True))
       .order_by("-criado_em")[:25]
```

O `order_by` explícito **não é redundante**: `annotate` agrupa a consulta e o
`Meta.ordering` do modelo deixa de valer. Sem essa linha, a ordem viria do banco,
sem garantia. É o tipo de detalhe que quebra silenciosamente numa refatoração —
está comentado no código por isso.

## As funções auxiliares

| Função | O que faz |
| --- | --- |
| `_porcentagem(parte, total)` | Uma casa decimal; devolve `0.0` se `total` for zero |
| `_com_cliques(consulta, *campos)` | Agrupa por um ou mais campos e já conta visitas, pessoas e cliques de WhatsApp |
| `_bloco(consulta, visitas, cliques)` | Cartão comparativo: visitas, pessoas, cliques, taxa **e engajamento** |
| `_totais(consulta)` | Visitas e pessoas de uma consulta, com `0` no lugar de `None` |
| `_serie_diaria(...)` | A série temporal com dias vazios preenchidos e as alturas das barras |
| `_engajamento(visitas)` | Rolagem e tempo das visitas medidas: proporções, mediana, média e as duas distribuições |
| `_mediana(valores)` | Mediana de uma lista, com média dos dois centrais quando o tamanho é par |
| `_distribuicao(valores, faixas)` | Quantos valores caem em cada faixa `[inicio, fim)`, com a fatia de cada uma |
| `_tempo_texto(segundos)` | `8s`, `45s`, `2min`, `3min 20s` |

`_SO_WHATSAPP = Q(cliques__evento__in=EVENTOS_WHATSAPP)` é o filtro de conversão,
definido uma vez no topo do módulo e reaproveitado em todo agrupamento. **É este
`Q` que define o que o painel chama de conversão**: mudar quais botões contam é
mudar `EVENTOS_WHATSAPP` em `models.py`, e todo o painel acompanha.

Como o filtro é aplicado na leitura, a mudança **alcança o histórico**: um código
acrescentado hoje faz os cliques antigos daquele botão entrarem na conta
retroativamente. É o oposto do `canal`, que fica gravado na visita.

## Contrato de saída de `montar(dias)`

```python
{
    "dias":            int,              # 1, 7, 30 ou 90
    "primeiro_dia":    date,
    "ultimo_dia":      date,
    "resumo":          {visitas, pessoas, cliques, taxa, robos, internos},
    "engajamento":     {medidas, total, cobertura, ate_o_fim, so_o_topo,
                        saida_rapida, rolagem_media, tempo_mediano,
                        tempo_mediano_texto, tempo_medio, tempo_medio_texto,
                        faixas_rolagem, faixas_tempo},
    "comparativo":     {"anuncio": {...}, "organico": {...}},   # + fatia e engajamento
    "por_canal":       [{canal, codigo, visitas, pessoas, cliques, taxa, fatia}],
    "campanhas":       [{campanha, conteudo, origem, visitas, pessoas, cliques, taxa}],
    "por_evento":      [{rotulo, total, pessoas, whatsapp, largura}],
    "por_dispositivo": [{dispositivo, visitas, cliques, fatia}],
    "serie":           [{dia, visitas, pessoas, anuncio, organico, cliques,
                         anuncio_altura, organico_altura}],
    "teto":            int,
    "ultimas":         [Visita, ...],    # 25, com cliques_whatsapp anotado
    "periodos":        PERIODOS,
}
```

A view acrescenta uma chave a esse dicionário antes de renderizar:
`aparelho_marcado`, lida do cookie `pf_interno`, que controla a seção "Suas
próprias visitas" no fim da página.

## Custo das consultas

`montar` dispara cerca de 20 consultas, quase todas agregações sobre colunas
indexadas (`criado_em`, `canal`, `robo`, `interno`, `evento`, `medido`). Em
SQLite, com o volume de uma landing page, isso é irrelevante — e a página é vista
por uma pessoa só, sem cache.

A exceção ao padrão é `_engajamento`, que traz os valores para a memória e conta
em Python — e é chamado **três vezes** por carregamento (total, anúncio,
orgânico). Se um dia o painel pesar, é o primeiro lugar a olhar; o segundo é a
série diária, que faz duas varreduras por período.

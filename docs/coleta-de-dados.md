# Coleta de dados

Tudo neste documento vive em [painel/coleta.py](../painel/coleta.py) — o coração
do projeto. É o arquivo que decide, para cada visita, **de onde a pessoa veio**.

## Princípio

Nada aqui identifica ninguém. O visitante recebe um número aleatório
(`uuid4().hex`) num cookie, e esse número só serve para separar "quantas
aberturas de página" de "quantas pessoas diferentes". Sem nome, sem e-mail, sem
rastreador de terceiros — nenhum dado sai do servidor.

E nada aqui pode derrubar a página: a criação da `Visita` está dentro de um
`try/except Exception` que registra o erro no log e devolve `visita = None`. Se o
banco cair, o site continua no ar e apenas o relatório fica sem o registro.

Este documento cobre o que é gravado **na chegada**. Rolagem e tempo de
permanência chegam depois, quando a pessoa sai da página, por outro caminho — veja
[medicao-de-leitura.md](medicao-de-leitura.md).

## Os três cookies

| Cookie | Conteúdo | Duração | Para quê |
| --- | --- | --- | --- |
| `pf_visitante` | 32 caracteres hexadecimais | 365 dias | Separar visitas de pessoas |
| `pf_origem` | Query string com `canal`, `origem`, `midia`, `campanha`, `conteudo`, `termo` | 90 dias | Manter a campanha valendo nas visitas seguintes |
| `pf_interno` | `"1"` | 730 dias | Marcar "este aparelho é do dono do site" |

Todos são gravados por `aplicar_cookies` com `httponly=True`,
`samesite="Lax"` e `secure` ligado quando a requisição é HTTPS. `httponly`
significa que o JavaScript da página não lê nenhum deles — a medição de clique
não precisa disso, ela usa o `data-visita` do HTML.

O `pf_visitante` é **validado** na leitura:
`re.fullmatch(r"[0-9a-f]{32}", visitante)`. Um cookie adulterado é descartado e
um número novo é gerado. Sem essa validação, qualquer texto colocado no cookie
entraria como identificador de pessoa.

## A decisão do canal

`_da_requisicao(request)` devolve `(dados, veio_marcada)`. A ordem de precedência
é esta, e o **primeiro** critério que casa decide:

```
1. Tem fbclid, gclid, ttclid, msclkid, gbraid, wbraid ou igshid?
   OU utm_medium contém cpc, ppc, paid, ads, anuncio, display, cpm, cpv,
      retargeting?
   -> ANUNCIO

2. Tem utm_source?
   -> SOCIAL      se for ig, instagram, fb, facebook, meta, linkedin,
                     tiktok, youtube, whatsapp, threads, twitter, x,
                     pinterest, kwai, telegram
   -> REFERENCIA  caso contrário

3. O referer é de buscador (google., bing., yahoo., duckduckgo., ecosia.,
   yandex., baidu., search.brave, ask.com, qwant., startpage.)?
   -> BUSCA

4. O referer é de rede social (instagram., facebook., fb.com, fb.me,
   linkedin., lnkd.in, t.co, twitter., x.com, tiktok., youtube., youtu.be,
   whatsapp., wa.me, pinterest., threads., reddit., telegram., t.me, kwai.)?
   -> SOCIAL

5. Existe algum referer?
   -> REFERENCIA

6. Nada disso?
   -> DIRETO, e veio_marcada = False
```

Três detalhes que só se descobrem lendo o código:

**`utm_source` tem precedência sobre o referer.** Se a URL traz
`utm_source=parceiro` e a pessoa veio do Google, o canal é `referencia`, não
`busca`. A marcação explícita ganha da inferência — quem marcou o link sabia o
que estava fazendo.

**A presença de um identificador de clique pago basta.** É o caso real do anúncio
do Instagram: o link chega só com `fbclid`, sem nenhum `utm`. Sem a lista
`CLIQUES_PAGOS`, essa visita cairia como "direto" e o anúncio pareceria não estar
trazendo ninguém.

**Quando não há `utm_source` mas há referer, o domínio vira `origem`.** É o que
faz a coluna "de onde" mostrar `www.google.com` em vez de vazio.

## O referer do próprio site não conta

`_host_do_referer` devolve vazio em dois casos: quando não há referer e **quando
ele é o próprio site** (`fabianopolone.com.br` ou qualquer subdomínio).

Navegar de uma âncora para outra dentro da página não é "veio de fora". Sem essa
regra, o relatório encheria de linhas falsas apontando para o próprio domínio.

O domínio está fixo na constante `DOMINIO` do módulo — ao trocar de domínio, é um
dos lugares que precisa mudar (o outro é `ALLOWED_HOSTS` em
[configuracao.md](configuracao.md)).

## A campanha continua valendo por 90 dias

O problema: a pessoa clica no anúncio, chega ao site, recarrega a página. A
segunda visita não tem `fbclid` nenhum — cairia como "direto", e o anúncio
perderia o crédito.

A solução, em duas funções:

- Quando a visita chega **marcada** (`veio_marcada = True`), `registrar_visita`
  guarda os campos de origem no cookie `pf_origem`, com 90 dias.
- Quando chega **sem marcação**, `_do_cookie(request)` recupera esses campos e a
  visita herda o canal, a campanha e o resto.

`_do_cookie` faz duas verificações antes de confiar no cookie: descarta se ele
passa de 800 caracteres, e **só aceita se `canal` for um valor válido de `Canal`**.
Um cookie adulterado (`canal=invadido`) é ignorado e a visita volta a ser
`direto` — há teste para exatamente isso.

Consequência prática ao ler o painel: numa janela de 90 dias após uma campanha,
visitas sem nenhum parâmetro continuam sendo atribuídas a ela. É o comportamento
desejado (é o modelo de atribuição "primeiro clique"), mas explica por que o
número de visitas de anúncio pode ser maior que o número de cliques que a
plataforma de anúncio reporta.

## Robôs

`_e_robo(agente)` procura 28 marcas no user-agent em minúsculas: `bot`, `crawl`,
`spider`, `slurp`, `facebookexternalhit`, `preview`, `curl`, `wget`,
`python-requests`, `httpx`, `go-http`, `headless`, `monitor`, `uptime`,
`pingdom`, `lighthouse`, `scanner`, `semrush`, `ahrefs`, `petalbot`, `applebot`,
`whatsapp`, `telegrambot`, `embed`, `archiver`, `validator`, `feedfetcher`,
`http-client`.

**User-agent vazio também é robô.** Navegador de verdade sempre manda um.

O motivo de existir essa lista: o Facebook abre o link toda vez que alguém o
compartilha, e o WhatsApp faz o mesmo para gerar a pré-visualização. Sem o filtro,
cada compartilhamento apareceria como visitante.

Note que `whatsapp` está tanto em `ROBOS` quanto em `REDES` — no primeiro caso é
o user-agent do pré-visualizador, no segundo é o domínio de onde a pessoa veio.
São campos diferentes da requisição, não há conflito.

## As visitas do dono do site

Quem cuida do site entra nele o tempo todo, e isso viraria movimento falso.

```
    Entrar no painel  ──────>  grava pf_interno = "1"  (730 dias)
                                          │
                               toda visita deste aparelho
                               é gravada com interno = True
                                          │
                               fica fora de todas as contas
                                          │
    Botão "voltar a contar"  ──>  apaga o cookie pf_interno
    (fim do painel)
```

`e_interno(request)` é uma linha:
`request.COOKIES.get(COOKIE_INTERNO) == "1"`.

**Estar logado não conta por si**, e isso é deliberado. Se contasse, quem
clicasse em "voltar a contar" continuaria fora dos números até a sessão expirar
(12 horas), e o botão pareceria quebrado. Uma chave só, o cookie.

Como é cookie, a marca vale **por aparelho e por navegador**. Quem usa celular e
computador precisa entrar no painel nos dois. E, se você entrar no painel do
computador de outra pessoa, o botão no fim do painel desfaz a marca.

## O IP real

`_endereco(request)` tenta três cabeçalhos, nesta ordem: `HTTP_X_REAL_IP`,
`HTTP_X_FORWARDED_FOR`, `REMOTE_ADDR`. Pega o primeiro valor antes da vírgula e
corta em 45 caracteres (tamanho de um IPv6).

O `REMOTE_ADDR` puro seria sempre o próprio servidor, porque o Django está atrás
do Nginx. A ordem depende, portanto, de o Nginx repassar esses cabeçalhos — veja
[deploy.md](deploy.md).

## Referência rápida das constantes

| Constante | Valor / tamanho | Onde é usada |
| --- | --- | --- |
| `COOKIE_VISITANTE` | `"pf_visitante"` | Identidade anônima |
| `COOKIE_ORIGEM` | `"pf_origem"` | Persistência da campanha |
| `COOKIE_INTERNO` | `"pf_interno"` | Marca do aparelho do dono |
| `DIAS_VISITANTE` | 365 | Duração do cookie de visitante |
| `DIAS_ORIGEM` | 90 | Janela de atribuição da campanha |
| `DIAS_INTERNO` | 730 | Duração da marca de aparelho |
| `DOMINIO` | `"fabianopolone.com.br"` | Detectar referer interno |
| `CLIQUES_PAGOS` | 7 parâmetros | Prova de clique pago |
| `MIDIAS_PAGAS` | 9 valores | `utm_medium` de campanha paga |
| `BUSCADORES` | 11 domínios | Classificar busca orgânica |
| `REDES` | 20 domínios | Classificar rede social por referer |
| `FONTES_REDES` | 15 valores | Classificar rede social por `utm_source` |
| `ROBOS` | 28 marcas | Detectar crawler |
| `CAMPOS_ORIGEM` | 6 nomes de campo | O que entra e sai do cookie de origem |

Ao acrescentar uma plataforma nova (um buscador, uma rede), o lugar é uma dessas
tuplas — e vale acrescentar um teste em [painel/tests.py](../painel/tests.py),
onde a classe `ClassificacaoDaOrigem` já cobre cada caminho da decisão.

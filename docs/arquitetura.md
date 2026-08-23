# Arquitetura

## Estrutura de arquivos

```
SIte_PolloniFlow/
│
├── manage.py                       Entrada da linha de comando do Django
├── requirements.txt                Django + gunicorn, nada mais
├── db.sqlite3                      Banco de dados — FORA do Git
├── README.md                       Guia curto de operação
├── docs/                           Esta documentação
│
├── polloniflow/                    Projeto Django (configuração)
│   ├── settings.py                 Toda a configuração, num arquivo só
│   ├── urls.py                     Rotas de nível raiz
│   └── wsgi.py                     Ponto de entrada do gunicorn
│
├── landing/                        App público — a página
│   ├── views.py                    Uma função: home()
│   └── (sem models, sem urls, sem migrations)
│
├── painel/                         App de medição e relatório
│   ├── models.py                   Visita, Clique, Canal, Dispositivo, EVENTOS
│   ├── coleta.py                   Registra visitas; decide o canal de origem
│   ├── relatorio.py                Calcula os números do painel, engajamento incluído
│   ├── views.py                    entrar, sair, painel, contagem, evento, medida
│   ├── urls.py                     Rotas /painel/..., /evento/ e /medida/
│   ├── apps.py                     Configuração do app
│   ├── tests.py                    49 testes
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   ├── 0002_clique_interno_visita_interno.py
│   │   └── 0003_visita_medido_visita_rolagem_visita_segundos.py
│   ├── management/commands/
│   │   └── criar_painel.py         Cria/redefine o acesso ao painel
│   ├── templates/painel/
│   │   ├── base.html               Esqueleto com noindex
│   │   ├── entrar.html             Tela de login
│   │   └── dashboard.html          O painel inteiro
│   └── static/painel/css/
│       └── painel.css
│
├── templates/landing/
│   └── index.html                  A página inteira
│
└── static/landing/
    ├── css/styles.css
    ├── js/main.js                  Medição (cliques + leitura) e animações
    └── img/                        favicons, hero em 3 larguras (webp+jpg), foto
```

Duas convenções de template convivem: a landing usa o diretório global
`templates/` (registrado em `TEMPLATES["DIRS"]`), e o painel usa
`painel/templates/painel/` (encontrado por `APP_DIRS`). Ambas funcionam; a do
painel é a que mantém o app autocontido.

## Mapa de rotas

Definidas em [polloniflow/urls.py](../polloniflow/urls.py) e
[painel/urls.py](../painel/urls.py):

| Rota | Nome | View | Acesso | Método |
| --- | --- | --- | --- | --- |
| `/` | `home` | `landing.views.home` | Público | GET |
| `/evento/` | `evento` | `painel.views.evento` | Público, sem CSRF | POST |
| `/medida/` | `medida` | `painel.views.medida` | Público, sem CSRF | POST |
| `/painel/` | `painel` | `painel.views.painel` | Login | GET |
| `/painel/entrar/` | `entrar` | `painel.views.entrar` | Público | GET, POST |
| `/painel/sair/` | `sair` | `painel.views.sair` | Público | POST |
| `/painel/contagem/` | `contagem` | `painel.views.contagem` | Login | POST |
| `/favicon.ico` | — | `RedirectView` (301) | Público | GET |

Três observações sobre essa tabela:

**`/evento/` e `/medida/` são curtos de propósito** — são chamados pela própria
página, a cada clique e a cada saída, e o endereço viaja em toda requisição de
medição.

**As duas rotas de medição são `@csrf_exempt`** porque o aviso vai por
`sendBeacon`, que não carrega cabeçalho personalizado. As duas compartilham a
mesma defesa, `_visitas_desta_pessoa`: só mexem numa visita que seja daquele
visitante e tenha menos de 24 horas.

**O redirecionamento de `/favicon.ico`** existe porque navegador antigo e robô de
busca pedem esse caminho na raiz, ignorando as tags do `<head>`. Sem a linha,
cada visita gerava um 404 no log.

## O caminho de uma visita

```
Navegador        Nginx          Django                        SQLite
    |              |               |                             |
    | GET /        |               |                             |
    |------------->| X-Forwarded-  |                             |
    |              |--Proto:https->| landing.views.home          |
    |              |               |                             |
    |              |               | coleta.registrar_visita()   |
    |              |               |  - le/cria pf_visitante     |
    |              |               |  - classifica o canal        |
    |              |               |    (utm, fbclid, referer)   |
    |              |               |  - detecta robo e aparelho  |
    |              |               |  - le o cookie pf_interno   |
    |              |               |  - INSERT Visita ---------->|
    |              |               |                             |
    |              |               | render index.html           |
    |              |               |  data-visita="{{ visita.id }}"
    |              |               |                             |
    |              |               | aplicar_cookies()           |
    |<-------------+---------------| Set-Cookie: pf_visitante,   |
    |  HTML + cookies              |             pf_origem       |
    |                                                            |
    | (a pessoa clica em "Falar agora")                          |
    |                                                            |
    | navigator.sendBeacon("/evento/", {evento, visita})         |
    |-----------------------------> painel.views.evento          |
    |                               - o codigo esta em EVENTOS?  |
    |                               - a visita e desta pessoa?    |
    |                               - foi nas ultimas 24h?        |
    |                               - INSERT Clique ------------>|
    |<------------------------------ 204 No Content              |
    |                                                            |
    | (a pessoa sai da pagina: visibilitychange / pagehide)      |
    |                                                            |
    | sendBeacon("/medida/", {visita, rolagem, segundos})        |
    |-----------------------------> painel.views.medida          |
    |                               - apara os valores           |
    |                               - as mesmas defesas          |
    |                               - UPDATE medido/rolagem/     |
    |                                 segundos com Greatest ---->|
    |<------------------------------ 204 No Content              |
```

Três coisas importantes nesse fluxo:

1. **A visita é gravada no servidor, antes de o HTML sair.** Bloqueador de
   anúncio e JavaScript desligado não afetam a contagem de visitas — só o clique e
   a medida de leitura dependem de JavaScript, e a marca `medido` é o que separa
   "não foi medido" de "saiu na hora".
2. **O id da visita volta para o navegador** dentro de
   `<body data-visita="...">`, e é ele que amarra o clique à visita.
3. **`/evento/` e `/medida/` sempre respondem 204**, aconteça o que acontecer. Um
   clique inválido, uma visita inexistente, um valor absurdo ou uma falha de banco
   não produzem erro visível — a página nunca deve quebrar por causa da medição.

## O caminho do painel

```
GET /painel/  ->  @login_required
                  - sem sessão: 302 para /painel/entrar/   (LOGIN_URL)
                  - com sessão:
                      relatorio.periodo_valido(GET["dias"])  -> 1|7|30|90
                      relatorio.montar(dias)
                        - filtra Visita e Clique: robo=False, interno=False
                        - monta 9 blocos de agregação (ver relatorio.md)
                        - devolve o dicionário de contexto
                      render dashboard.html
                      Cache-Control: no-store
```

O `no-store` está lá porque a página tem dado de negócio e é servida atrás de um
proxy: nada de painel guardado em cache intermediário ou no botão "voltar".

## Decisões de arquitetura e o motivo

**Um app por responsabilidade, não por tela.** `landing` serve a página;
`painel` mede e relata. Se um dia houver uma segunda página pública, ela entra em
`landing` e a medição continua funcionando sem alteração.

**A coleta é uma biblioteca, não um middleware.** `painel/coleta.py` expõe
funções que a view chama de propósito. Um middleware registraria toda requisição
— inclusive `/evento/`, os arquivos estáticos e o próprio painel — e a contagem
viraria lixo. Assim, só a página que interessa é medida, e isso fica explícito em
uma linha de [landing/views.py](../landing/views.py).

**O canal é decidido na gravação, não na leitura.** A classificação acontece uma
vez, quando a visita chega, e fica gravada na coluna `canal`. Consequência
prática: mudar as regras de classificação **não** reclassifica o histórico. O
relatório também fica rápido, porque só agrupa por uma coluna indexada.

**O `Clique` copia `canal`, `robo` e `interno` da visita.** É duplicação
deliberada: o relatório por canal continua correto mesmo se a visita for apagada
numa limpeza futura (a FK é `SET_NULL`, não `CASCADE`).

**A medição de leitura é acumulativa, não substitutiva.** `/medida/` grava com
`Greatest`, então o maior valor já visto vence e um segundo aviso menor não apaga o
primeiro. E a atualização é feita em uma consulta só, sem `SELECT` + `save()`, para
que dois avisos que cheguem juntos não desfaçam um ao outro. Veja
[medicao-de-leitura.md](medicao-de-leitura.md#por-que-greatest).

**Sem camada de serviço, sem repositório, sem serializer.** O projeto tem seis
views e um relatório. A abstração a mais custaria mais do que resolve.

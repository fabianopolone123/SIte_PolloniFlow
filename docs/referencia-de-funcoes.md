# Referência de funções

Catálogo de tudo que é chamável no projeto, arquivo por arquivo. Funções com
`_` no início são privadas ao módulo.

---

## `landing/views.py`

### `home(request)`
A única view pública. Registra a visita, renderiza a página e devolve os cookies.

```python
def home(request):
    visita, cookies = registrar_visita(request)
    resposta = render(request, "landing/index.html", {"visita": visita})
    return aplicar_cookies(resposta, cookies, seguro=request.is_secure())
```

Passa `visita` ao template — que usa `visita.id` no `data-visita` do `<body>`. Se
o registro falhar, `visita` é `None` e o filtro `default_if_none:''` no template
deixa o atributo vazio; o JavaScript então não envia clique nem medida alguma (a
constante `temVisita` em `main.js` desliga as duas coisas).

---

## `painel/coleta.py`

Detalhes das regras em [coleta-de-dados.md](coleta-de-dados.md).

### Públicas

#### `registrar_visita(request) -> (Visita | None, list[tuple])`
Grava a visita e devolve `(visita, cookies)`, onde `cookies` é uma lista de
`(nome, valor, dias)` que ainda **não** foram aplicados à resposta.

O que faz, em ordem: valida ou cria o `pf_visitante`; classifica a origem com
`_da_requisicao`; se a visita veio marcada, agenda o cookie `pf_origem`, senão
tenta herdar a origem de `_do_cookie`; lê user-agent, referer, dispositivo, IP,
robô e a marca interna; insere a linha.

**Nunca levanta exceção.** Falha de banco é registrada com
`registro.exception(...)` e a função devolve `visita = None`.

#### `aplicar_cookies(resposta, cookies, seguro) -> resposta`
Aplica a lista de cookies numa resposta. Converte dias em segundos
(`dias * 24 * 60 * 60`) e fixa `httponly=True`, `samesite="Lax"` e
`secure=seguro`. Chamada por `landing.views.home` e por
`painel.views._marcar_aparelho`.

#### `e_interno(request) -> bool`
`True` se o cookie `pf_interno` vale `"1"`. **Estar logado não conta** — veja o
motivo em [coleta-de-dados.md](coleta-de-dados.md#as-visitas-do-dono-do-site).

### Privadas

| Função | Devolve | O que faz |
| --- | --- | --- |
| `_texto(valor, tamanho)` | `str` | Trata `None`, aplica `strip()` e corta no tamanho |
| `_host_do_referer(request)` | `(host, referer)` | Domínio e URL do referer; `("", "")` se não houver ou se for o próprio site |
| `_dispositivo(agente)` | `Dispositivo` | Tablet, celular ou computador pelo user-agent (tablet é testado primeiro) |
| `_e_robo(agente)` | `bool` | `True` se o user-agent casa com `ROBOS` **ou está vazio** |
| `_endereco(request)` | `str \| None` | IP real, de `X-Real-IP`, `X-Forwarded-For` ou `REMOTE_ADDR` |
| `_da_requisicao(request)` | `(dados, veio_marcada)` | A decisão do canal a partir de utm, identificador pago e referer |
| `_do_cookie(request)` | `dict \| None` | Recupera a origem guardada; `None` se ausente, longa demais ou com canal inválido |

---

## `painel/relatorio.py`

Detalhes de cada conta em [relatorio.md](relatorio.md).

### Públicas

#### `periodo_valido(valor) -> int`
Converte o `?dias=` da URL num dos valores de `PERIODOS` (1, 7, 30, 90). Qualquer
outra coisa vira `PERIODO_PADRAO` (30). É a única validação de entrada do painel.

#### `montar(dias) -> dict`
Monta o contexto inteiro do painel. Filtra `robo=False, interno=False` em tudo e
devolve as 14 chaves listadas em
[relatorio.md](relatorio.md#contrato-de-saída-de-montardias).

### Privadas

| Função | Devolve | O que faz |
| --- | --- | --- |
| `_porcentagem(parte, total)` | `float` | Porcentagem com uma casa; `0.0` se `total` for zero |
| `_com_cliques(consulta, *campos)` | QuerySet | Agrupa por campos, contando visitas, pessoas e cliques de WhatsApp |
| `_bloco(consulta, visitas, cliques)` | `dict` | Cartão comparativo: visitas, pessoas, cliques, taxa e engajamento do lado |
| `_totais(consulta)` | `dict` | `{visitas, pessoas}`, com `0` no lugar de `None` |
| `_serie_diaria(visitas, cliques, primeiro_dia, ultimo_dia)` | `(serie, teto)` | Série diária com dias vazios preenchidos e alturas das barras |
| `_engajamento(visitas)` | `dict` | Rolagem e tempo das visitas com `medido=True`; devolve tudo zerado se não houver nenhuma |
| `_mediana(valores)` | `int` | Mediana; média arredondada dos dois centrais quando o tamanho é par |
| `_distribuicao(valores, faixas)` | `list[dict]` | Quantos valores caem em cada faixa `[inicio, fim)`, com a fatia |
| `_tempo_texto(segundos)` | `str` | `8s`, `45s`, `2min`, `3min 20s` |

Constantes do módulo: `PERIODOS`, `PERIODO_PADRAO`, `_SO_WHATSAPP`, `ATE_O_FIM`
(90), `SO_O_TOPO` (25), `SAIDA_RAPIDA` (10), `FAIXAS_ROLAGEM`, `FAIXAS_TEMPO` —
ver [medicao-de-leitura.md](medicao-de-leitura.md#os-três-limites).

---

## `painel/views.py`

### `entrar(request)`
Login do painel. `GET` mostra o formulário; `POST` autentica com
`django.contrib.auth.authenticate` e exige `pessoa.is_active`.

Ao entrar com sucesso, **marca o aparelho** (`_marcar_aparelho`) antes de
redirecionar: quem entra no painel num aparelho está dizendo que o aparelho é
dele. Se já estiver autenticado, redireciona direto para o painel.

Erro é uma string simples (`"Usuário ou senha incorretos."`) passada ao template
— não usa `django.contrib.messages`, que não está instalado.

### `sair(request)`
`@require_POST`. Faz `logout` e redireciona para a tela de entrada. Só POST, para
que um link ou uma pré-carga não desloguem ninguém.

**Não apaga o cookie `pf_interno`** — sair do painel não faz suas visitas voltarem
a contar. Isso é feito só pelo botão da seção "Suas próprias visitas".

### `painel(request)`
`@login_required`. Chama `relatorio.montar(relatorio.periodo_valido(request.GET.get("dias")))`,
acrescenta `aparelho_marcado` ao contexto, renderiza `dashboard.html` e responde
com `Cache-Control: no-store`.

### `contagem(request)`
`@login_required @require_POST`. Liga e desliga a contagem deste aparelho:

- `acao == "contar"` → apaga o cookie `pf_interno`; as visitas voltam a contar.
- qualquer outro valor → grava o cookie; as visitas param de contar.

Redireciona para o painel nos dois casos.

### `evento(request)`
`@csrf_exempt @require_POST`. Recebe o aviso de clique. **Responde 204 sempre.**

Sem proteção de CSRF de propósito: o aviso é enviado por `sendBeacon`, que não
carrega cabeçalhos, e o pedido não faz nada além de gravar uma linha de
estatística. Em compensação, exige duas coisas:

1. o código do botão está em `EVENTOS`;
2. `_visitas_desta_pessoa` encontra a visita — ou seja, ela é **daquele
   visitante** e foi criada nas **últimas 24 horas**.

Falhando qualquer uma, nada é gravado — e a resposta continua 204. Exceção do
banco é engolida com `except Exception: pass`, pela mesma razão: medição não
derruba nada.

A validação de dono da visita mora em `_visitas_desta_pessoa`, compartilhada com
`medida`.

### `medida(request)`
`@csrf_exempt @require_POST`. Recebe quanto da página a pessoa viu e quanto tempo
ficou. **Responde 204 sempre.**

Chega por `sendBeacon` quando a pessoa sai da página, e pode chegar mais de uma
vez — quem volta para a aba e sai de novo manda outro aviso. Por isso a gravação
usa `Greatest`, numa consulta só:

```python
_visitas_desta_pessoa(request).update(
    medido=True,
    rolagem=Greatest("rolagem", Value(rolagem)),
    segundos=Greatest("segundos", Value(segundos)),
)
```

Fica sempre o maior valor já visto, e dois avisos simultâneos não desfazem um ao
outro. As defesas são as mesmas de `/evento/`. Detalhes em
[medicao-de-leitura.md](medicao-de-leitura.md).

### `_visitas_desta_pessoa(request)`
Privada. Devolve o **queryset** com a visita informada, se ela for mesmo daquela
pessoa (cookie `pf_visitante`) e tiver menos de 24 horas; `Visita.objects.none()`
quando não confere. Também recusa identificador com mais de 18 dígitos.

Devolve queryset em vez do objeto de propósito: é o que permite a `medida`
atualizar em uma consulta só, sem corrida entre dois avisos que cheguem juntos.
Usada por `evento` (com `.first()`) e por `medida` (com `.update()`).

### `_inteiro(valor, teto)`
Privada. `max(0, min(int(float(valor)), teto))`, com `0` para qualquer coisa
inconvertível. O `float` no meio é necessário: o navegador pode mandar `"12.7"`, e
`int("12.7")` levantaria `ValueError`.

### `_marcar_aparelho(resposta, request)`
Privada. Grava `pf_interno = "1"` por `DIAS_INTERNO` (730) na resposta dada.

Constante do módulo: `LIMITE_SEGUNDOS = 30 * 60` — o teto do tempo de
permanência.

---

## `painel/models.py`

Estrutura completa em [modelo-de-dados.md](modelo-de-dados.md).

| Nome | Tipo | Papel |
| --- | --- | --- |
| `Canal` | `TextChoices` | anuncio, busca, social, referencia, direto |
| `Dispositivo` | `TextChoices` | celular, tablet, computador |
| `EVENTOS` | `dict` | Lista de permissão dos 8 botões medidos, na ordem do relatório |
| `EVENTOS_WHATSAPP` | `tuple` | Os três botões que contam como conversão |
| `Visita` | `Model` | Uma abertura da página |
| `Visita.__str__` | método | `"Anúncio pago em 12/08/2026 14:30"` |
| `Clique` | `Model` | Um clique num botão medido |
| `Clique.rotulo` | `@property` | Nome legível do evento, com o código como fallback |
| `Clique.__str__` | método | `"Falar agora (botão do topo) em 12/08/2026 14:31"` |

---

## `painel/management/commands/criar_painel.py`

### `Command.handle(*args, **opcoes)`
Cria o acesso ao painel se ele não existir.

| Argumento | Padrão | Efeito |
| --- | --- | --- |
| `--usuario` | `fabiano` | Nome de usuário |
| `--senha` | `1234` | Senha a gravar |
| `--trocar-senha` | desligado | Redefine a senha de um acesso que já existe |

Usa `get_or_create(username=...)`. **Sem `--trocar-senha`, um acesso existente
tem a senha preservada** — por isso o comando pode rodar em toda publicação sem
risco, e é o que o `deploy.sh` faz.

`set_password` não passa pelos validadores de senha do Django (que recusariam
`1234`). É de propósito: a senha é escolhida por quem roda o comando.

```powershell
# Trocar a senha do acesso que já existe
.venv\Scripts\python manage.py criar_painel --senha "uma-senha-de-verdade" --trocar-senha
```

---

## `polloniflow/`

| Objeto | Arquivo | Papel |
| --- | --- | --- |
| `urlpatterns` | `urls.py` | `/`, as rotas do painel e da medição, e o redirecionamento de `/favicon.ico` |
| `application` | `wsgi.py` | Callable WSGI que o gunicorn carrega |
| — | `settings.py` | Configuração; ver [configuracao.md](configuracao.md) |
| `main()` | `../manage.py` | Fixa `DJANGO_SETTINGS_MODULE` e delega ao Django |

---

## `static/landing/js/main.js`

Não há módulo nem exportação — o arquivo roda de cima a baixo ao carregar.

A ordem do arquivo é deliberada: **a medição vem primeiro**. Antes ela ficava no
fim, depois da animação de fundo, e qualquer erro no canvas levava junto o
registro dos cliques — o relatório mostrava zero sem que ninguém soubesse por quê.

| Função / bloco | O que faz |
| --- | --- |
| `enviar(endereco, dados)` | `navigator.sendBeacon`, com `fetch({keepalive: true})` de reserva quando ele falha ou não existe |
| `profundidade()` | Quanto da página está vista, de 0 a 100; página que cabe na tela vale 100 |
| `marcarRolagem()` | Guarda o maior valor de `profundidade()` já visto |
| `acumularTempo()` | Soma o tempo desde a última marca **só** se a página estiver visível |
| `enviarMedida()` | Manda rolagem e segundos para `/medida/`; não repete aviso idêntico ao anterior |
| Medição de cliques | Para cada `[data-evento]`, envia o clique para `/evento/` e chama `enviarMedida()` junto |
| Aparições ao rolar | `IntersectionObserver` (limiar 0,14) que põe `is-visible`; sem suporte, mostra tudo direto |
| `criarParticulas()` | Até 34 partículas no celular (< 760 px) e 86 no computador |
| `redimensionar()` | Ajusta o canvas ao `devicePixelRatio` e recria as partículas |
| `desenhar()` | Laço de `requestAnimationFrame`: move, desenha e liga os pares a menos de 128 px |
| `tocar()` / `parar()` | Ligam e desligam o laço; a animação para com a aba escondida |

Três disparadores enviam a medida: `visibilitychange` para `hidden`, `pagehide`
(o aviso de saída que o Safari do iPhone respeita) e cada clique medido.

`sendBeacon` é essencial e não é preferência de estilo: o clique no WhatsApp tira
a pessoa da página, e um `fetch` comum seria cancelado antes de chegar ao
servidor. Note que `enviar` testa o **retorno** de `sendBeacon` — ele devolve
`false` quando a fila está cheia, e nesse caso o `fetch` assume.

---

## Índice alfabético

| Nome | Arquivo |
| --- | --- |
| `_bloco` | `painel/relatorio.py` |
| `_com_cliques` | `painel/relatorio.py` |
| `_da_requisicao` | `painel/coleta.py` |
| `_dispositivo` | `painel/coleta.py` |
| `_distribuicao` | `painel/relatorio.py` |
| `_do_cookie` | `painel/coleta.py` |
| `_e_robo` | `painel/coleta.py` |
| `_endereco` | `painel/coleta.py` |
| `_engajamento` | `painel/relatorio.py` |
| `_host_do_referer` | `painel/coleta.py` |
| `_inteiro` | `painel/views.py` |
| `_marcar_aparelho` | `painel/views.py` |
| `_mediana` | `painel/relatorio.py` |
| `_porcentagem` | `painel/relatorio.py` |
| `_serie_diaria` | `painel/relatorio.py` |
| `_tempo_texto` | `painel/relatorio.py` |
| `_texto` | `painel/coleta.py` |
| `_totais` | `painel/relatorio.py` |
| `_visitas_desta_pessoa` | `painel/views.py` |
| `aplicar_cookies` | `painel/coleta.py` |
| `contagem` | `painel/views.py` |
| `Command.handle` | `painel/management/commands/criar_painel.py` |
| `e_interno` | `painel/coleta.py` |
| `entrar` | `painel/views.py` |
| `evento` | `painel/views.py` |
| `home` | `landing/views.py` |
| `medida` | `painel/views.py` |
| `montar` | `painel/relatorio.py` |
| `painel` | `painel/views.py` |
| `periodo_valido` | `painel/relatorio.py` |
| `registrar_visita` | `painel/coleta.py` |
| `sair` | `painel/views.py` |

# Desenvolvimento

## Ambiente

Windows, PowerShell, com a `.venv` dentro da pasta do projeto (ignorada pelo Git).

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py criar_painel
$env:DJANGO_DEBUG = "True"; .venv\Scripts\python manage.py runserver
```

- Site: <http://127.0.0.1:8000/>
- Painel: <http://127.0.0.1:8000/painel/> — usuário `fabiano`, senha `1234`

`DJANGO_DEBUG=True` não é opcional para desenvolver: sem ele os cookies saem com
`Secure`, o navegador os descarta em HTTP e o login do painel parece quebrado.
Veja [configuracao.md](configuracao.md#debug-e-o-que-ele-muda).

O `$env:` vale só para aquele terminal. Para fixar na sessão:

```powershell
$env:DJANGO_DEBUG = "True"
.venv\Scripts\python manage.py runserver
```

## Testes

```powershell
.venv\Scripts\python manage.py test painel
```

**52 testes**, todos passando (verificado em 22/08/2026, Django 5.2.17). Rodam
contra um banco temporário — nunca tocam o `db.sqlite3`.

As nove classes, e o que cada uma protege:

| Classe | Testes | Cobre |
| --- | --- | --- |
| `ClassificacaoDaOrigem` | 12 | Cada caminho da decisão de canal: utm pago, `fbclid`, `gclid`, busca, Instagram, outro site, direto, referer interno, herança de campanha, cookie adulterado, robô, dispositivo |
| `RegistroDeCliques` | 4 | Clique válido grava com o canal da visita; código inventado, visitante de outra pessoa e visita inexistente não gravam nada |
| `MedidaDeLeitura` | 8 | `/medida/` grava rolagem e tempo; visita nasce sem medida; aviso menor não apaga o maior; valores absurdos são aparados; medida de outra pessoa é ignorada |
| `RelatorioDeEngajamento` | 8 | Quem rolou até o fim; a mediana como tempo típico; visita não medida fora das médias; período sem medida não quebra; robô e visita interna fora; anúncio e orgânico com o próprio engajamento |
| `BotaoFlutuante` | 3 | A página traz o atalho flutuante; o clique nele conta como WhatsApp; a página informa o endereço da medição |
| `ConversaoContaTodoBotaoQueAbreConversa` | 3 | O botão principal do topo conta como conversa e aponta mesmo para o WhatsApp; âncora e menu não contam |
| `PaginaLimpa` | 3 | Nenhum comentário de template vaza para o HTML; a faixa não promete número que ninguém mediu; o rosto de quem responde está na página |
| `AcessoAoPainel` | 3 | O painel exige login; o acesso criado pelo comando entra; senha errada não |
| `VisitasDoDono` | 8 | Entrar marca o aparelho; visita e clique marcados ficam fora do relatório; dá para desligar e religar; visitante qualquer não mexe na contagem |

Quatro testes merecem menção porque documentam decisão, não só código:

`test_cookie_de_origem_adulterado_e_ignorado` — põe `canal=invadido` no cookie e
exige que a visita volte a ser `direto`. É a validação de `_do_cookie`.

`test_da_para_voltar_a_contar_o_aparelho` — clica em "voltar a contar" e exige que
a visita seguinte conte, **mesmo com a sessão do painel ainda aberta**. É o teste
que trava a decisão de o cookie ser a única chave.

`test_segundo_aviso_menor_nao_apaga_o_maior` — trava o uso de `Greatest` em
`/medida/`. Sem ele, uma refatoração para `save()` passaria despercebida e a
rolagem registrada cairia.

`test_a_faixa_nao_promete_numero_que_ninguem_mediu` — trava uma decisão de
conteúdo, não de código: a página não volta a exibir número inventado.

### Rodar um subconjunto

```powershell
.venv\Scripts\python manage.py test painel.tests.ClassificacaoDaOrigem
.venv\Scripts\python manage.py test painel.tests.RelatorioDeEngajamento
.venv\Scripts\python manage.py test painel.tests.VisitasDoDono.test_visita_marcada_fica_fora_do_relatorio
.venv\Scripts\python manage.py test painel -v 2      # nome de cada teste
```

### O que não é testado

O bloco de engajamento tem boa cobertura (`RelatorioDeEngajamento`), mas os
**outros** blocos do relatório continuam sem: as agregações por canal, por
campanha, por evento, por aparelho e a série diária. Ao mexer em algum deles, o
caminho mais rápido para conferir é criar visitas no shell e olhar o painel — ou,
melhor, escrever o teste que falta.

O JavaScript não tem teste de execução: `BotaoFlutuante` e `PaginaLimpa` conferem o
HTML entregue, não o comportamento do `main.js`. A rolagem e o tempo são testados
do lado do servidor (`MedidaDeLeitura`), com o POST direto em `/medida/`.

O CSS não tem teste algum, e não há linter configurado.

## Comandos do dia a dia

```powershell
# Criar migração depois de mexer em models.py
.venv\Scripts\python manage.py makemigrations painel

# Aplicar
.venv\Scripts\python manage.py migrate

# Ver o que ainda não foi aplicado
.venv\Scripts\python manage.py showmigrations painel

# Conferir se o projeto está consistente
.venv\Scripts\python manage.py check

# Shell com o Django carregado
.venv\Scripts\python manage.py shell

# Trocar a senha do painel
.venv\Scripts\python manage.py criar_painel --senha "nova-senha" --trocar-senha

# Reunir os estáticos (só faz sentido em produção)
.venv\Scripts\python manage.py collectstatic
```

## Convenções

**O código é em português.** Nomes de função, variável, campo, rota e template.
`registrar_visita`, não `register_visit`. Siga isso — metade da legibilidade do
projeto vem daí.

**Comentário explica o porquê, não o quê.** O padrão do projeto é comentar decisão
não óbvia: por que `/evento/` é `csrf_exempt`, por que `set_password` ignora os
validadores, por que o `order_by` explícito não é redundante. Comentário que
repete o código não combina com o que já está lá.

**Sem dependência nova sem necessidade real.** Duas linhas em
`requirements.txt` é uma qualidade do projeto, não um acidente.

**Falha de medição não derruba a página.** Todo caminho novo de coleta deve
seguir o padrão de `registrar_visita`, `evento` e `medida`: capturar exceção,
responder 204 e seguir.

## Receitas

### Acrescentar um botão medido

1. Registre o código e o nome em `EVENTOS`, em
   [painel/models.py](../painel/models.py) — a posição no dicionário é a posição
   no relatório.
2. Ponha `data-evento="o_codigo"` no `<a>` ou `<button>` em
   [templates/landing/index.html](../templates/landing/index.html).

Nada mais. O JavaScript pega qualquer `[data-evento]`, e `/evento/` só aceita
código que esteja na lista.

**Se o botão abrir conversa no WhatsApp, acrescente o código a
`EVENTOS_WHATSAPP` também** — é essa tupla que define conversão, e todo o painel
acompanha. Um botão de WhatsApp fora dela faz a taxa sair menor do que a real, sem
nenhum sinal de erro. Vale um teste em `ConversaoContaTodoBotaoQueAbreConversa`,
que já cobre os dois lados: o que conta e o que não conta.

### Acrescentar um período ao painel

Uma entrada em `PERIODOS`, em [painel/relatorio.py](../painel/relatorio.py):

```python
PERIODOS = ((1, "Hoje"), (7, "7 dias"), (30, "30 dias"), (90, "90 dias"), (180, "180 dias"))
```

`periodo_valido` valida a partir dessa tupla e o template gera os filtros a partir
dela.

### Reconhecer uma plataforma nova de tráfego

Acrescente à tupla certa em [painel/coleta.py](../painel/coleta.py):
`CLIQUES_PAGOS` (identificador de clique pago), `MIDIAS_PAGAS` (`utm_medium`),
`BUSCADORES`, `REDES` (domínio de referer), `FONTES_REDES` (`utm_source`) ou
`ROBOS`.

Lembre que **isso não reclassifica o histórico** — o canal é decidido na gravação.
Vale acrescentar um teste em `ClassificacaoDaOrigem`, que já tem um caso por
caminho de decisão.

### Trocar o domínio

Três lugares: `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` em
[polloniflow/settings.py](../polloniflow/settings.py), e a constante `DOMINIO` em
[painel/coleta.py](../painel/coleta.py) — esquecer a terceira faz o próprio site
aparecer no relatório como site de origem.

### Trocar o número do WhatsApp

**Quatro** ocorrências de `wa.me/5514988208134` em
[templates/landing/index.html](../templates/landing/index.html) — cabeçalho, hero,
fim da página e atalho flutuante —, cada uma com uma mensagem pré-preenchida
diferente. As mensagens são o que permite saber, já na conversa, de onde a pessoa
saiu; ao trocar o número, preserve essa diferença.

### Trocar a arte do hero

O `<picture>` usa três larguras em WebP mais um JPEG de reserva. Depois de
substituir o `hero-automation.png`, regenere as versões com o script Pillow que
está no [README.md](../README.md#a-imagem-do-topo). O Pillow **não** entra no
`requirements.txt`: é ferramenta de edição, usada só nessa hora.

Confira também o `preload` no `<head>`, que precisa apontar para o mesmo `srcset`
do `<picture>` — se divergir, o navegador baixa duas imagens.

### Mexer nos limites da medição de leitura

Os três limites (`ATE_O_FIM`, `SO_O_TOPO`, `SAIDA_RAPIDA`) e as duas tuplas de
faixas estão no topo de [painel/relatorio.py](../painel/relatorio.py); o teto de
tempo (`LIMITE_SEGUNDOS`) está em [painel/views.py](../painel/views.py).

Mudar um limite **reinterpreta o histórico** na hora, porque a conta é feita na
leitura — ao contrário do canal, que fica gravado. Mudar o teto de tempo, não: ele
é aplicado na gravação, e os valores já aparados continuam aparados.

### Popular o banco local com dados de teste

```powershell
.venv\Scripts\python manage.py shell
```

```python
from django.test import Client
c = Client()  # o mesmo cliente mantém os cookies entre as chamadas
CELULAR = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile Safari/604"

# visita de anúncio
c.get("/?utm_source=ig&utm_medium=paid&utm_campaign=Agosto", HTTP_USER_AGENT=CELULAR)

# visita de busca orgânica
Client().get("/", HTTP_USER_AGENT=CELULAR,
             HTTP_REFERER="https://www.google.com/search?q=automacao")

# um clique de WhatsApp na última visita
from painel.models import Visita
v = Visita.objects.latest("id")
c.post("/evento/", {"evento": "whatsapp_topo", "visita": v.pk})

# e a medida de leitura dessa visita: rolou 95% e ficou 2 minutos
c.post("/medida/", {"visita": v.pk, "rolagem": 95, "segundos": 120})
```

Cuidado ao fazer isso com o banco de produção baixado por `scp` — os dados de
teste ficam misturados ao histórico real.

## Depuração

**Os números de leitura não aparecem.** Confira a cobertura no pé do bloco: se for
0%, nenhuma visita do período foi medida. Causas comuns: o `data-medida-url` não
está no `<body>` (rota renomeada), o `main.js` deu erro antes do bloco de medição,
ou todas as visitas do período são anteriores à migração 0003.

**A visita não foi registrada.** A exceção está no log, não no banco:
`registro.exception("Não foi possível registrar a visita")`. Em desenvolvimento
sai no console do `runserver`; em produção, no journal do serviço.

**O clique não aparece no painel.** Confira, na ordem: o código está em `EVENTOS`?
O `<body>` tem `data-visita` preenchido (a visita foi registrada)? A visita tem
menos de 24 horas? O aparelho está marcado como interno — nesse caso o clique
**foi** gravado, com `interno=True`, e está fora das contas de propósito.

**O painel mostra zero com movimento real.** Provavelmente o aparelho está
marcado. O bloco "Suas próprias visitas", no fim do painel, diz o estado e mostra
quantas visitas internas houve no período.

**Login do painel não funciona local.** `DJANGO_DEBUG=True` esquecido.

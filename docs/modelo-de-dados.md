# Modelo de dados

Duas tabelas, definidas em [painel/models.py](../painel/models.py). Nenhum outro
app do projeto tem modelo. As tabelas de autenticação e de sessão são as padrão
do Django (`auth_user`, `django_session`).

```
Visita  1 ────< N  Clique
        (on_delete=SET_NULL)
```

## Enumerações

### `Canal` — de onde a pessoa veio

O eixo principal de todo o painel.

| Valor no banco | Rótulo exibido | Quando é atribuído |
| --- | --- | --- |
| `anuncio` | Anúncio pago | Identificador de clique pago (`fbclid`, `gclid`…) ou `utm_medium` de campanha paga |
| `busca` | Busca orgânica | Referer de buscador, sem marcação de campanha |
| `social` | Redes sociais | Referer de rede social, ou `utm_source` conhecido de rede |
| `referencia` | Outros sites | Qualquer outro referer, ou `utm_source` desconhecido |
| `direto` | Direto | Nenhuma pista — é o **padrão** do campo |

A regra completa e a ordem de precedência estão em
[coleta-de-dados.md](coleta-de-dados.md#a-decisão-do-canal).

No painel, "orgânico" significa **tudo que não é `anuncio`** — busca, social,
referência e direto juntos.

### `Dispositivo`

| Valor | Rótulo | Deduzido de |
| --- | --- | --- |
| `celular` | Celular | `mobi`, `iphone`, `android`, `phone`, `ipod` no user-agent |
| `tablet` | Tablet | `ipad`, `tablet`, ou `android` sem `mobile` |
| `computador` | Computador | O restante — é o **padrão** |

A ordem importa: tablet é testado antes de celular, porque um iPad manda
`Mobile` no user-agent e cairia em celular se a ordem fosse invertida.

## `EVENTOS` — os botões medidos

Não é um modelo, é um dicionário em [painel/models.py](../painel/models.py), e
funciona como uma lista de permissão. **Só código presente aqui é aceito** pela
rota `/evento/` — assim ninguém cria evento novo mandando requisição na mão.

| Código | Rótulo no relatório | Onde está na página |
| --- | --- | --- |
| `whatsapp_flutuante` | Botão flutuante do WhatsApp | Atalho fixo, acompanha a rolagem |
| `whatsapp_topo` | Falar agora (botão do topo) | Botão do cabeçalho |
| `whatsapp_final` | Chamar no WhatsApp (final da página) | Seção de chamada final |
| `diagnostico` | Solicitar diagnóstico | Botão primário do hero |
| `ver_solucoes` | Ver soluções | Botão secundário do hero |
| `menu_solucoes` | Menu: Soluções | Navegação |
| `menu_processo` | Menu: Processo | Navegação |
| `menu_contato` | Menu: Contato | Navegação |

A ordem do dicionário é a ordem em que os eventos aparecem no relatório — o
flutuante vem primeiro porque é o atalho disponível em qualquer altura da página.

`EVENTOS_WHATSAPP = ("whatsapp_flutuante", "whatsapp_topo", "whatsapp_final")` — a
tupla dos botões que levam à conversa. **É ela que define conversão**: quando o
painel diz "cliques" ou "taxa", está contando apenas estes três.

Note que `diagnostico`, apesar de hoje apontar para o WhatsApp na página, **não**
está em `EVENTOS_WHATSAPP` — ele conta como interesse, não como conversão.

## `Visita`

Uma abertura da página inicial. Recarregar gera uma linha nova.

| Campo | Tipo | Índice | O que guarda |
| --- | --- | --- | --- |
| `id` | BigAutoField | PK | — |
| `criado_em` | DateTimeField (`auto_now_add`) | ✓ | Quando a página foi aberta |
| `visitante` | CharField(32) | ✓ | UUID hexadecimal do cookie `pf_visitante`. Separa "visitas" de "pessoas" |
| `canal` | CharField(20), choices `Canal` | ✓ | Classificação da origem; padrão `direto` |
| `origem` | CharField(120) | | `utm_source`, ou o domínio do referer se não houver utm |
| `midia` | CharField(120) | | `utm_medium` |
| `campanha` | CharField(180) | | `utm_campaign` |
| `conteudo` | CharField(180) | | `utm_content` — usado como "criativo" no relatório |
| `termo` | CharField(180) | | `utm_term` |
| `referencia` | CharField(300) | | URL completa do referer, vazia se for o próprio site |
| `caminho` | CharField(300) | | `request.get_full_path()` — o caminho com a query string |
| `dispositivo` | CharField(20), choices `Dispositivo` | | Padrão `computador` |
| `agente` | CharField(300) | | User-agent bruto |
| `ip` | GenericIPAddressField (nulo) | | IP real, lido dos cabeçalhos do Nginx |
| `robo` | BooleanField | ✓ | Crawler ou pré-visualizador de link. Fora das contas |
| `interno` | BooleanField | ✓ | Visita do dono do site. Fora das contas |
| `medido` | BooleanField | ✓ | O navegador chegou a informar rolagem e tempo |
| `rolagem` | PositiveSmallIntegerField | | Quanto da página foi vista, de 0 a 100 |
| `segundos` | PositiveIntegerField | | Segundos com a página à vista; teto de 30 minutos |

`Meta.ordering = ("-criado_em",)` — mais recente primeiro, por padrão.

Os três últimos campos não são preenchidos na gravação: chegam depois, por
`sendBeacon`, quando a pessoa sai da página. Toda a mecânica está em
[medicao-de-leitura.md](medicao-de-leitura.md).

`medido` é o campo que impede uma leitura errada dos outros dois. Uma visita com
`rolagem=0, segundos=0` e `medido=False` significa "não foi observada", não "foi
embora na hora" — e o relatório a exclui das médias por isso.

Todo campo de texto tem tamanho máximo e é truncado na gravação (função `_texto`
em `coleta.py`), nunca em branco por `null`: os campos de texto usam
`blank=True`, não `null=True`. Só `ip` aceita nulo.

### Por que `robo` e `interno` são gravados em vez de descartados

Ambos existem para **não perder informação**. O robô é sinal de que o link está
sendo compartilhado; a visita interna é sinal de que você mexeu no site. Os dois
ficam no banco e são simplesmente filtrados na hora de contar, e o painel mostra
o total de cada um no bloco de resumo — é assim que se percebe que o filtro está
trabalhando.

## `Clique`

Um acionamento de botão medido.

| Campo | Tipo | Índice | O que guarda |
| --- | --- | --- | --- |
| `id` | BigAutoField | PK | — |
| `criado_em` | DateTimeField (`auto_now_add`) | ✓ | Quando clicou |
| `evento` | CharField(40) | ✓ | Um código de `EVENTOS` |
| `visita` | FK → `Visita`, `SET_NULL`, `related_name="cliques"` | ✓ (FK) | A visita em que o clique aconteceu |
| `canal` | CharField(20), choices `Canal` | ✓ | **Copiado** da visita |
| `robo` | BooleanField | ✓ | **Copiado** da visita |
| `interno` | BooleanField | ✓ | **Copiado** da visita |

`Meta.ordering = ("-criado_em",)`.

`rotulo` é uma `@property` que traduz o código pelo dicionário `EVENTOS`, com o
próprio código como fallback — assim um evento removido de `EVENTOS` ainda
aparece legível no histórico.

### Por que os três campos são copiados

A FK é `SET_NULL`: se um dia as visitas antigas forem apagadas para enxugar o
banco, os cliques sobrevivem. Com `canal`, `robo` e `interno` copiados no momento
do clique, o relatório por canal continua correto mesmo com `visita = NULL`.

O efeito colateral a conhecer: **os campos copiados não se atualizam**. Se a
visita fosse reclassificada depois, o clique manteria o canal antigo. Hoje nada
no código reclassifica visita, então não há divergência.

## Migrações

| Arquivo | O que faz |
| --- | --- |
| [0001_initial.py](../painel/migrations/0001_initial.py) | Cria `Visita` e `Clique` |
| [0002_clique_interno_visita_interno.py](../painel/migrations/0002_clique_interno_visita_interno.py) | Acrescenta `interno` nas duas tabelas, com `default=False` e índice |
| [0003_visita_medido_visita_rolagem_visita_segundos.py](../painel/migrations/0003_visita_medido_visita_rolagem_visita_segundos.py) | Acrescenta `medido`, `rolagem` e `segundos` em `Visita` |

A migração 0002 é a que trouxe o recurso "não contar as visitas do dono". Por
usar `default=False`, todo o histórico anterior fica marcado como visita externa
— inclusive as visitas suas que existiam antes dela.

A 0003 trouxe a medição de leitura. Pelo mesmo motivo — `default=False` em
`medido` —, **todo o histórico anterior a ela fica fora das médias de rolagem e
tempo**, o que é exatamente o desejado: aquelas visitas não foram observadas. É
também por isso que a cobertura mostrada no painel sobe aos poucos, conforme as
visitas novas entram.

## Consultas úteis no shell

```powershell
.venv\Scripts\python manage.py shell
```

```python
from painel.models import Visita, Clique, Canal

# Quantas visitas reais (sem robô, sem você) existem no total
Visita.objects.filter(robo=False, interno=False).count()

# As últimas 10 visitas de anúncio, com a campanha
list(Visita.objects.filter(canal=Canal.ANUNCIO, robo=False, interno=False)
     .values_list("criado_em", "campanha", "conteudo")[:10])

# Todos os cliques de WhatsApp, do mais novo para o mais antigo
from painel.models import EVENTOS_WHATSAPP
Clique.objects.filter(evento__in=EVENTOS_WHATSAPP, robo=False, interno=False).count()

# Quantas visitas suas o filtro está tirando da conta
Visita.objects.filter(interno=True).count()
```

Lembre-se de que **não existe Django Admin** neste projeto: o shell e o painel são
as duas formas de olhar os dados.

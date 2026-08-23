# Frontend

Sem bundler, sem npm, sem framework. Três arquivos de CSS/JS servidos pelo
`staticfiles` do Django e templates do Django. A única dependência externa da
página é a fonte Inter, do Google Fonts.

## A landing page

[templates/landing/index.html](../templates/landing/index.html) — uma página só,
com âncoras internas.

### Estrutura

| Seção | `id` | Conteúdo |
| --- | --- | --- |
| `<canvas class="network-canvas">` | `networkCanvas` | Fundo animado de partículas, `aria-hidden` |
| `header.site-header` | — | Marca, navegação (3 âncoras) e botão "Falar agora" |
| `section.hero` | `top` | Título, pergunta, texto, dois botões, três reforços e a faixa de áreas atendidas |
| `section.metrics` | — | Três compromissos: sob medida, você aprova antes, perguntar é de graça |
| `section.section` | `solucoes` | Quatro cartões de solução |
| `section.flow-section` | — | Texto + painel visual do fluxo (Entrada → Validação → Sistema → Resultado) |
| `section.section` | `processo` | Quatro etapas do método |
| `section.cta-section` | `contato` | Chamada final, o bloco "quem responde sou eu" com foto e o botão grande |
| `footer.site-footer` | — | Marca e slogan |
| `a.whatsapp-flutuante` | — | Atalho fixo para o WhatsApp, fora do `<main>` |

O `<head>` traz, além dos favicons: `canonical`, sete metatags Open Graph +
`twitter:card` e um `preload` da imagem do hero. Os dois primeiros grupos existem
porque o link é compartilhado justamente onde o público está — sem eles, o link no
WhatsApp e no Instagram aparece como texto seco, sem imagem nem título.

### O texto da página é argumento, não enfeite

Vale saber, antes de editar: a página **não** fala em terceira pessoa nem promete
número. Dois comentários no template registram a decisão.

Onde havia três indicadores — `24/7`, `-80%`, `+1` — hoje há três compromissos. O
motivo está escrito no arquivo: número que não sai de medição nenhuma faz o
visitante duvidar do resto da página, ainda mais numa empresa que ele não conhece.
Os compromissos que entraram no lugar dependem só de como o trabalho é feito, e
portanto dá para cumprir sempre.

O nome da empresa saiu do `<h1>` porque o selo do topo já o mostra, e em tela de
celular a linha inteira quebrava em duas de caixa-alta.

Há um teste que trava as duas coisas: `PaginaLimpa` verifica que nenhum comentário
`{% comment %}` vaza para o HTML e que a faixa de compromissos não promete número
que ninguém mediu.

### O que o template recebe do Django

Apenas `visita`, e ela aparece em três atributos do `<body>`:

```html
<body data-visita="{{ visita.id|default_if_none:'' }}"
      data-evento-url="{% url 'evento' %}"
      data-medida-url="{% url 'medida' %}">
```

Esses três atributos são **toda a interface entre o backend e a medição**. O
`default_if_none:''` cobre o caso de o registro da visita ter falhado — o
JavaScript então não envia nem clique nem medida.

### Os botões medidos

Oito elementos com `data-evento`. Os quatro de conversão apontam para
`wa.me/5514988208134`, cada um com uma mensagem pré-preenchida diferente — é o que
permite saber, já na conversa, de onde a pessoa saiu:

| Elemento | `data-evento` | Conversão? |
| --- | --- | --- |
| Atalho flutuante | `whatsapp_flutuante` | sim |
| Botão do cabeçalho | `whatsapp_topo` | sim |
| Botão do fim da página | `whatsapp_final` | sim |
| Botão primário do hero | `diagnostico` | sim |
| Botão secundário do hero | `ver_solucoes` | não — leva a uma âncora |
| Três links do menu | `menu_*` | não — levam a âncoras |

O número do WhatsApp está escrito **quatro vezes** no HTML — ao trocá-lo, troque
em todas.

### O atalho flutuante

```html
<a class="whatsapp-flutuante" href="https://wa.me/..." data-evento="whatsapp_flutuante"
   aria-label="Pedir orçamento sem compromisso pelo WhatsApp">
```

É um **link comum com SVG embutido**, fora do `<main>`: aparece mesmo se o
JavaScript não rodar, e não depende de nenhuma biblioteca de ícone. O `aria-label`
existe porque o rótulo visível ("Pedir orçamento") não diz o canal.

### Imagens responsivas

O hero é servido por `<picture>`: WebP em três larguras (800, 1200, 1717) com um
JPEG de 1200 como reserva. O `hero-automation.png` original (1,4 MB) **não é mais
usado pela página** — ficou no repositório só como fonte para gerar as versões.

O `preload` no `<head>` repete o mesmo `srcset` e o mesmo `sizes` que o
`<picture>` usa. Isso é necessário para o navegador escolher o mesmo arquivo e não
baixar duas imagens; a imagem do topo é o maior elemento da página, e sem o
preload ela só começaria a baixar depois do CSS.

A foto do bloco "quem responde sou eu" segue o mesmo padrão em escala menor: WebP
`1x`/`2x` com JPEG de reserva, exibida a 56 px, com `loading="lazy"` e
`decoding="async"`. A versão de 224 px existe para tela retina e aguenta até
112 px sem perder nitidez.

O comando para regenerar as versões (com Pillow, que **não** está no
`requirements.txt` porque é ferramenta de edição, não dependência do site) está no
[README.md](../README.md#a-imagem-do-topo).

## O JavaScript

[static/landing/js/main.js](../static/landing/js/main.js) — sem módulo, sem
build; roda de cima a baixo.

**A ordem do arquivo é deliberada.** A medição vem primeiro, e o comentário no
topo explica: antes ela ficava no fim, depois da animação de fundo, e qualquer erro
no canvas levava junto o registro dos cliques — o painel mostrava zero sem que
ninguém soubesse por quê.

A ordem é: envio → rolagem e tempo → cliques → aparições ao rolar → animação de
fundo. Do mais importante para o mais decorativo.

### `enviar` — o transporte

```javascript
function enviar(endereco, dados) {
    if (!endereco) return;
    if (navigator.sendBeacon && navigator.sendBeacon(endereco, dados)) return;
    fetch(endereco, { method: "POST", body: dados, keepalive: true }).catch(() => {});
}
```

`sendBeacon` é obrigatório, não estilo: o clique no WhatsApp tira a pessoa da
página, e um `fetch` comum seria cancelado na saída. É também o motivo de
`/evento/` e `/medida/` serem `@csrf_exempt` — `sendBeacon` não carrega cabeçalho
personalizado.

Note que o **retorno** é testado: `sendBeacon` devolve `false` quando a fila do
navegador está cheia, e nesse caso o `fetch` assume.

### Rolagem e tempo

`profundidade()` devolve 0 a 100; uma página que cabe inteira na tela vale 100.
`marcarRolagem()` guarda só o maior valor já visto, ligado a `scroll` e `resize`
com `{ passive: true }`.

`acumularTempo()` soma o tempo desde a última marca **apenas** se
`document.visibilityState === "visible"` — aba no fundo e celular no bolso não são
tempo de leitura.

`enviarMedida()` acumula, marca, monta `"rolagem:segundos"` e **não repete aviso
idêntico ao anterior**. Dispara em três momentos: `visibilitychange` para
`hidden`, `pagehide` (o aviso de saída que o Safari do iPhone respeita) e junto de
cada clique medido — este último para mostrar se o botão convence no começo da
página ou só depois dela toda.

O que acontece do outro lado está em
[medicao-de-leitura.md](medicao-de-leitura.md).

### Aparições ao rolar

`IntersectionObserver` com limiar 0,14 põe `is-visible` e para de observar. Sem
suporte ao observador, os itens recebem a classe direto — **o conteúdo nunca fica
escondido** por falta de JavaScript.

### Animação de fundo

Três cuidados que valem preservar ao mexer:

- **`prefers-reduced-motion: reduce` desliga a animação inteira.** O canvas nem é
  inicializado.
- **O laço para com a aba escondida** (`tocar`/`parar` em `visibilitychange`), o
  que poupa bateria.
- **Menos partículas no celular**: 34 abaixo de 760 px de largura, 86 acima. O
  desenho compara cada partícula com todas as outras, então o custo sobe com o
  quadrado da quantidade — a conta cai para um quarto e a página deixa de esquentar
  o aparelho.

## O painel

Três templates em [painel/templates/painel/](../painel/templates/painel/):

**`base.html`** — esqueleto com `<meta name="robots" content="noindex, nofollow">`,
os mesmos favicons do site e `painel.css`. Blocos `titulo` e `corpo`.

**`entrar.html`** — formulário de login com `{% csrf_token %}`,
`autocomplete="username"` / `current-password`, o erro em `<p class="erro">` e um
link de volta para o site.

**`dashboard.html`** — o painel inteiro: um `<header class="topo">` com usuário,
link para o site e o formulário de sair; depois dez `<section class="secao">`, uma
por bloco de [relatorio.md](relatorio.md), na ordem: filtros de período, resumo,
quanto leram e quanto tempo ficaram, anúncio ou orgânico, visitas por dia, de onde
vieram, campanhas, cliques nos botões, aparelhos, últimas visitas e "Suas próprias
visitas".

O bloco de engajamento é o único condicional: `{% if engajamento.medidas %}`
esconde os números quando não houve medida nenhuma no período, em vez de mostrar
uma fileira de zeros.

### Gráficos sem biblioteca

Não há Chart.js nem SVG gerado. Os gráficos são `div`s com altura ou largura em
porcentagem, calculadas no Python:

```html
<i class="fatia anuncio"  style="height:{{ linha.anuncio_altura|unlocalize }}%"></i>
<i class="fatia organico" style="height:{{ linha.organico_altura|unlocalize }}%"></i>
```

O `{% load l10n %}` e o filtro `|unlocalize` no topo do template existem por um
motivo específico: com `LANGUAGE_CODE = "pt-br"`, o Django escreveria `12,5` no
lugar de `12.5`, e o CSS não entende vírgula decimal. O mesmo se aplica ao
`?dias={{ valor|unlocalize }}` dos filtros de período.

**Ao acrescentar qualquer número dentro de um atributo `style` ou de uma URL neste
template, use `|unlocalize`.** É o erro mais fácil de cometer aqui.

## As cores

### Site — [static/landing/css/styles.css](../static/landing/css/styles.css)

Variáveis em `:root`: fundo `#06111f`, texto `#f7fbff`, apagado `#a9bacb`, e as
cores de marca ciano `#42d9ff`, verde `#59e39b`, lima `#b9f25d`, laranja
`#ffb35c`. Fundo com dois `radial-gradient` sobre um `linear-gradient` diagonal.
Fonte Inter, com `system-ui` e `Segoe UI` como reserva.

O arquivo cresceu bastante no ajuste de celular — é onde vivem o atalho
flutuante, o bloco `.quem-responde`, a faixa `.hero-reforco` e os pontos de quebra
do hero.

### Painel — [painel/static/painel/css/painel.css](../painel/static/painel/css/painel.css)

O painel tem uma decisão de cor documentada no próprio arquivo, e que vale
respeitar ao editar:

> As cores dos gráficos **não** são as cores da marca. O ciano e o verde do site
> são claros demais para virar dado sobre fundo escuro (ficam fora da faixa de
> luminosidade e quase iguais entre si para quem não distingue cores). As três
> abaixo foram conferidas contra a superfície `#0b1d2b`: separação para
> protanopia/deuteranopia acima do alvo e contraste acima de 3:1. O ciano da
> marca continua na interface (títulos, botões), nunca no dado.

| Papel | Cor | Onde |
| --- | --- | --- |
| Orgânico | `#3987e5` | Barras e marcadores de tráfego não pago |
| Anúncio | `#d95926` | Barras e marcadores de tráfego pago |
| Cliques | `#199e70` | Conversões |
| Marca | `#42d9ff` | Títulos, botões, links — **nunca dado** |

Ao acrescentar uma série nova ao painel, escolha a cor pelo mesmo critério:
distinguível em protanopia e deuteranopia, contraste acima de 3:1 contra
`#0b1d2b`.

## Arquivos estáticos

`static/landing/img/` contém:

| Arquivo | Uso |
| --- | --- |
| `favicon.svg` | O principal |
| `favicon.ico` | Reserva para navegador antigo (16/32/48) |
| `apple-touch-icon.png` | iOS |
| `hero-automation-{800,1200,1717}.webp` | O hero, por largura |
| `hero-automation-1200.jpg` | Reserva do hero e imagem do Open Graph |
| `hero-automation.png` | Fonte original, 1,4 MB — **não usado pela página** |
| `fabiano-112.webp`, `fabiano-224.webp`, `fabiano-112.jpg` | A foto do bloco de contato |

Em produção, `manage.py collectstatic` reúne tudo em `staticfiles/` (fora do Git)
e o Nginx serve daí. Em desenvolvimento com `DEBUG=True`, o Django serve direto de
`STATICFILES_DIRS`.

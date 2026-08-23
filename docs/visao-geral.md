# Visão geral

## O que é

Um site institucional de uma página de **Fabiano Polloni**, que faz automação,
software sob medida e integrações, no ar em
<https://fabianopolone.com.br>.

O site não vende nem cadastra nada. Ele tem um único objetivo de conversão:
**levar o visitante para uma conversa no WhatsApp**. Todo o resto do projeto
existe para medir se isso está acontecendo e de onde vêm as pessoas que
acontecem.

## As duas metades

```
┌─────────────────────────────┐        ┌─────────────────────────────┐
│  app landing                │        │  app painel                 │
│  A página que o visitante vê│───────▶│  Registra e relata           │
│  /                          │ grava  │  /painel/  /evento/          │
│  público                    │        │  protegido por senha         │
└─────────────────────────────┘        └─────────────────────────────┘
```

**`landing`** — uma view, um template. Serve a página inicial. É o app público.

**`painel`** — três responsabilidades: registrar cada visita, cada clique e a
leitura de cada página (`coleta.py` e `views.py`), calcular os números
(`relatorio.py`) e mostrá-los numa tela protegida por login (`views.py` +
templates).

A dependência é numa direção só: `landing` importa de `painel`
(`landing/views.py` chama `painel.coleta`), nunca o contrário.

## Por que um painel próprio

O site poderia usar Google Analytics. Não usa, por três motivos que estão
escritos no código:

1. **Nenhum dado sai do servidor.** Não há rastreador de terceiros, nenhum
   pixel, nenhum script externo além da fonte do Google Fonts.
2. **A pergunta é específica e única:** *o anúncio pago está trazendo gente que
   chama no WhatsApp?* O painel responde exatamente isso, com anúncio e orgânico
   lado a lado em todo bloco — e, quando a resposta é "não", a medição de leitura
   diz qual dos dois motivos possíveis está agindo: a pessoa saiu antes de ler, ou
   leu tudo e não se convenceu. Veja
   [medicao-de-leitura.md](medicao-de-leitura.md).
3. **Bloqueador de anúncio não atrapalha.** A medição é feita no servidor, no
   mesmo domínio.

O custo dessa escolha: o painel é de uso pessoal, com um login só, e o histórico
existe em um único arquivo SQLite. Veja [deploy.md](deploy.md#o-banco-é-o-ativo).

## Tecnologia

| Peça | Escolha | Onde |
| --- | --- | --- |
| Framework | Django 5.2.17 | [requirements.txt](../requirements.txt) |
| Python | 3.13 | `.venv` |
| Banco | SQLite | [polloniflow/settings.py](../polloniflow/settings.py) |
| Servidor de aplicação | gunicorn | [requirements.txt](../requirements.txt) |
| Servidor web / TLS | Nginx (na VPS) | [deploy.md](deploy.md) |
| Frontend | HTML + CSS + JavaScript puro | [frontend.md](frontend.md) |

**Nenhuma dependência além de Django e gunicorn.** Sem DRF, sem Celery, sem
Redis, sem bundler, sem framework de frontend. O `INSTALLED_APPS` não inclui nem
`django.contrib.admin` nem `django.contrib.messages` — o painel é a única
interface administrativa, e não há Django Admin neste projeto.

## Vocabulário do código

O código é escrito **em português**: nomes de função, de variável, de campo do
banco, de rota e de template. Ao mexer, siga isso — `registrar_visita`, não
`register_visit`.

Os termos com significado preciso:

| Termo | Significa |
| --- | --- |
| **Visita** | Uma abertura da página inicial. Recarregar a página gera uma visita nova. |
| **Visitante** | Uma pessoa, identificada por um número aleatório em cookie que dura 365 dias. Uma pessoa pode ter muitas visitas. |
| **Pessoas** (nos relatórios) | Contagem de visitantes distintos. |
| **Canal** | De onde a visita veio: anúncio pago, busca orgânica, redes sociais, outros sites ou direto. É o eixo principal de todo o painel. |
| **Clique** | O acionamento de um botão marcado com `data-evento` na página. |
| **Conversão** | Um clique num dos quatro botões que abrem o WhatsApp. A taxa é cliques ÷ visitas. |
| **Robô** | Visita de crawler ou de pré-visualização de link. Gravada, mas fora de todas as contas. |
| **Interno** | Visita do próprio dono do site, reconhecida por cookie de aparelho. Gravada, mas fora de todas as contas. |
| **Orgânico** | No painel, tudo que **não** é anúncio pago — inclui busca, social não paga, referência e direto. |
| **Rolagem** | Quanto da página a pessoa chegou a ver, de 0 a 100. A partir de 90 conta como "viu até o fim". |
| **Segundos** | Tempo com a página à vista. Aba no fundo não conta; o teto é de 30 minutos. |
| **Medido** | A visita chegou a informar rolagem e tempo. O que não foi medido fica fora das médias. |
| **Cobertura** | De quantas visitas do período os números de leitura realmente saíram. |

## O que o projeto deliberadamente não faz

Saber disso evita "consertar" o que é decisão:

- **Não identifica ninguém.** Sem nome, e-mail, formulário ou login de visitante.
  O cookie de visitante é um UUID aleatório sem qualquer vínculo com a pessoa.
- **Não usa JavaScript para registrar a visita.** A visita é gravada no servidor
  ao renderizar a página. Só o *clique* e a *medida de leitura* dependem de JS — e,
  para que essa dependência não distorça as médias, a visita carrega a marca
  `medido`, que separa "não foi observada" de "saiu na hora".
- **Não deixa a medição derrubar o site.** `registrar_visita` engole qualquer
  exceção do banco: a página continua no ar, só o registro se perde.
- **Não apaga robô nem visita interna.** Ambos são gravados; a exclusão acontece
  na hora de contar, em [relatorio.md](relatorio.md).

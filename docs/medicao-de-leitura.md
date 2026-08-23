# Medição de leitura

O bloco mais novo do projeto, e o que responde a pergunta que a taxa de conversão
não responde: **por que a pessoa não chamou?**

## O problema

A conversão sozinha diz que ninguém clicou, não diz o motivo. E os dois motivos
possíveis pedem correções opostas:

| Sinal | Diagnóstico | Onde mexer |
| --- | --- | --- |
| Rolou pouco, ficou poucos segundos | Saiu antes de ler | No anúncio ou no topo da página |
| Leu tudo e não chamou | A oferta não convenceu | No texto, no preço, na prova |

Sem rolagem e tempo, os dois casos aparecem no painel exatamente iguais: uma
visita sem clique.

## O que é medido

Dois números por visita, contados pelo navegador e enviados para `/medida/`:

**`rolagem`** — quanto da página a pessoa chegou a ver, de 0 a 100. A partir de
**90** conta como "até o fim": os últimos por cento são rodapé, e exigir 100
marcaria como abandono quem leu tudo o que importa. Uma página que cabe inteira
na tela já vale 100.

**`segundos`** — tempo com a página **à vista**. Aba no fundo e celular no bolso
não contam: o contador só acumula enquanto `document.visibilityState` é
`visible`.

E uma marca:

**`medido`** — falsa até o primeiro aviso chegar. É ela que separa "ficou zero
segundo" de "o navegador não chegou a contar".

## Por que `medido` existe

É a decisão mais importante deste bloco. Sem essa marca, três grupos de visitas
entrariam nas médias como abandono imediato:

1. as gravadas **antes** desta medição existir (todo o histórico anterior à
   migração 0003);
2. quem fechou a página antes do JavaScript rodar;
3. robôs e qualquer cliente que não execute JS.

Nenhum desses foi observado saindo rápido — simplesmente não foi observado. Por
isso `_engajamento` só olha `visitas.filter(medido=True)`, e o painel mostra a
**cobertura**: de quantas visitas, das quantas houve, o número realmente saiu.

Ao ler o bloco no painel, a cobertura é a primeira linha a conferir. Cobertura
baixa com números extremos é ruído, não descoberta.

## Os três limites

Constantes no topo de [painel/relatorio.py](../painel/relatorio.py):

| Constante | Valor | Significa |
| --- | --- | --- |
| `ATE_O_FIM` | 90 | Rolagem a partir da qual conta como "viu a página inteira" |
| `SO_O_TOPO` | 25 | Abaixo disso, viu só a primeira tela e foi embora |
| `SAIDA_RAPIDA` | 10 | Menos que isso em segundos, não deu tempo de ler nem o título |

E o teto do tempo, em [painel/views.py](../painel/views.py):

`LIMITE_SEGUNDOS = 30 * 60` — meia hora. O navegador já só conta tempo à vista,
mas uma aba deixada aberta no primeiro plano a tarde inteira ainda somaria horas e
sozinha estragaria a média.

## As faixas

Duas distribuições, para ver a forma e não só a média:

```python
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
```

Os intervalos são `[inicio, fim)`, e `None` no fim significa "sem teto" — por isso
a faixa de rolagem termina em 101, para incluir o 100.

## Mediana, não média

O painel mostra a mediana como "tempo típico". O motivo está no código:

> A mediana diz mais que a média aqui: uma aba esquecida aberta puxa a média para
> cima sozinha, e a mediana ignora esse tipo de exagero.

A média aparece ao lado, entre parênteses, como referência. Quando as duas se
afastam muito, é sinal de que há poucas visitas muito longas.

`_tempo_texto` formata para leitura de relance: `8s`, `45s`, `2min`,
`3min 20s`.

## O caminho do aviso

```
Navegador                                      Django
   │
   │  scroll / resize  ->  rolagemMaxima = max(...)
   │  visibilitychange ->  acumula segundos só quando visível
   │
   │  a pessoa sai da página
   │   (visibilitychange -> hidden, ou pagehide)
   │
   ├─ sendBeacon("/medida/", {visita, rolagem, segundos}) ─────>  medida()
   │                                                              ├ _inteiro(rolagem, 100)
   │                                                              ├ _inteiro(segundos, 1800)
   │                                                              ├ a visita é desta pessoa? de hoje?
   │                                                              └ UPDATE medido=True,
   │                                                                   rolagem=Greatest(...),
   │                                                                   segundos=Greatest(...)
   │<───────────────────────────────────────────────────────────  204
```

O aviso também é enviado **junto com cada clique**, e por um motivo específico:
mandar o quanto a pessoa tinha lido até clicar é o que mostra se o botão convence
no começo da página ou só depois dela toda.

## Por que `Greatest`

O aviso pode chegar mais de uma vez: `visibilitychange` e `pagehide` podem
disparar os dois, e quem volta para a aba e sai de novo manda outro. Se o segundo
aviso simplesmente sobrescrevesse, um valor menor apagaria o maior.

```python
_visitas_desta_pessoa(request).update(
    medido=True,
    rolagem=Greatest("rolagem", Value(rolagem)),
    segundos=Greatest("segundos", Value(segundos)),
)
```

Fica sempre o maior já visto, e a atualização acontece **numa consulta só** — sem
`SELECT` seguido de `save()`, dois avisos que chegam juntos não desfazem um ao
outro. É por isso que `_visitas_desta_pessoa` devolve um queryset em vez do
objeto.

Do lado do navegador há uma economia complementar: `enviarMedida` guarda o último
resumo enviado (`"rolagem:segundos"`) e não repete aviso idêntico.

## As defesas

As mesmas de `/evento/`, e pelos mesmos motivos:

| Defesa | Onde |
| --- | --- |
| `@csrf_exempt` porque `sendBeacon` não manda cabeçalho | decorador |
| Só mexe na visita se ela for **daquela pessoa** (cookie `pf_visitante`) | `_visitas_desta_pessoa` |
| Só se a visita for das **últimas 24 horas** | `_visitas_desta_pessoa` |
| Identificador com no máximo 18 dígitos | `_visitas_desta_pessoa` |
| Valor aparado em `[0, teto]`, e texto sem sentido vira 0 | `_inteiro` |
| Exceção de banco engolida | `try/except` |
| Resposta sempre 204 | fim da view |

`_inteiro` usa `int(float(valor))` de propósito: o navegador pode mandar
`"12.7"`, e `int("12.7")` levantaria `ValueError`.

## Onde isso aparece no painel

Dois lugares:

**O bloco "Quanto leram e quanto tempo ficaram"** — quatro números grandes
(chegaram ao fim, só a primeira tela, tempo típico, saída rápida), as duas
distribuições em barras e a linha de cobertura no pé.

**Os cartões de anúncio e orgânico** — cada lado traz o próprio engajamento
(`ate_o_fim`, `tempo_mediano_texto`, `rolagem_media`, `medidas`), o que permite
ver se o tráfego pago lê menos que o espontâneo. Foi por isso que `_bloco` passou
a receber o queryset além dos totais.

## Custo

`_engajamento` traz `rolagem` e `segundos` de todas as visitas medidas do período
para a memória (`values_list`) e calcula em Python: mediana, média, três
proporções e duas distribuições. É chamado **três vezes** por carregamento do
painel — uma para o total, uma para anúncio, uma para orgânico.

Para o volume de uma landing page isso é irrelevante. Se um dia pesar, o caminho
é trocar as contagens por agregação no banco; a mediana é a única que realmente
precisa dos valores em memória.

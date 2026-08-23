# Site Fabiano Polloni

Landing page em Django de Fabiano Polloni, no ar em
<https://fabianopolone.com.br>.

O site tem duas partes:

- a **página** que o visitante vê (app `landing`);
- um **painel de relatórios** protegido por senha (app `painel`), que mostra de
  onde vieram as visitas e quantas viraram conversa no WhatsApp.

A documentação completa do projeto — estrutura, funções, contexto e as
decisões de arquitetura — está na pasta [docs/](docs/README.md).

## Rodar localmente

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py criar_painel
$env:DJANGO_DEBUG = "True"; .venv\Scripts\python manage.py runserver
```

- Site: <http://127.0.0.1:8000/>
- Painel: <http://127.0.0.1:8000/painel/>

Os testes: `.venv\Scripts\python manage.py test painel`

---

## O painel de relatórios

Entre em `/painel/entrar/`. O acesso inicial é **usuário `fabiano`, senha
`1234`** — criado pelo comando `manage.py criar_painel`.

> **Troque essa senha.** Ela é a única coisa entre a internet e os seus dados de
> campanha:
>
> ```bash
> python manage.py criar_painel --senha "uma-senha-de-verdade" --trocar-senha
> ```
>
> O comando **não** mexe na senha de um acesso que já existe, a não ser com
> `--trocar-senha`. Por isso pode rodar em toda publicação sem risco.

### O que o painel responde

| Bloco | Pergunta |
| --- | --- |
| Resumo | Quantas visitas, quantas pessoas, quantos cliques para o WhatsApp e qual a taxa de conversão |
| Quanto leram e quanto tempo ficaram | Quem foi embora antes de ler e quem leu tudo e mesmo assim não chamou |
| Anúncio ou orgânico | Quanto do movimento veio de campanha paga e quanto veio sozinho — e qual dos dois converte melhor |
| Visitas por dia | O movimento ao longo do período, já separado entre anúncio e orgânico |
| De onde vieram | Anúncio, busca, redes sociais, outros sites, direto |
| Campanhas de anúncio | Uma linha por campanha e por criativo, com a conversão de cada um |
| Cliques nos botões | Quantas vezes cada botão da página foi clicado |
| Aparelhos | Celular, computador, tablet |
| Últimas visitas | As 25 mais recentes, uma a uma |

### Quanto leram e quanto tempo ficaram

A taxa de conversão sozinha diz que ninguém chamou, mas não diz por quê. Estas
duas medidas separam os dois motivos, que pedem correções opostas:

- **saiu antes de ler** (rolou pouco, ficou poucos segundos) → o problema está
  no anúncio ou no topo da página;
- **leu tudo e não chamou** → o problema está na oferta.

O navegador manda os dois números quando a pessoa sai da página, por
`sendBeacon`, para o endereço `/medida/`:

- **rolagem**: quanto da página ela chegou a ver, de 0 a 100. A partir de 90
  conta como "até o fim" — os últimos por cento são rodapé.
- **segundos**: tempo com a página *à vista*. Aba no fundo e celular no bolso
  não contam. O teto é de 30 minutos, para que uma aba esquecida aberta não
  estrague sozinha a média.

O aviso pode chegar mais de uma vez (quem volta para a aba e sai de novo manda
outro), então vale sempre o maior valor já registrado.

O painel mostra a **mediana** como "tempo típico", não a média: uma única aba
esquecida aberta levanta a média e não mexe na mediana.

#### Cobertura

Cada visita nasce com a marca `medido` desligada e só a recebe quando o primeiro
aviso chega. Isso separa "ficou zero segundo" de "não deu tempo de medir" — quem
fechou a página antes do JavaScript rodar, e todas as visitas gravadas antes
desta medição existir, ficam **fora** das médias em vez de entrarem como
abandono imediato. O painel mostra de quantas visitas o número saiu.

### Como a origem é decidida

Na ordem, para cada visita:

1. Tem `fbclid`, `gclid` ou `utm_medium` de campanha paga (`cpc`, `paid`, `ads`…)?
   → **Anúncio pago**.
2. Tem `utm_source`? → **Redes sociais** se for `ig`, `facebook`, `tiktok`…;
   senão **Outros sites**.
3. Veio de um buscador (`google`, `bing`, `duckduckgo`…)? → **Busca orgânica**.
4. Veio de uma rede social? → **Redes sociais**.
5. Veio de outro site qualquer? → **Outros sites**.
6. Nada disso? → **Direto**.

Quem chega pelo anúncio e depois recarrega a página **não** vira "direto": a
campanha fica guardada num cookie e continua valendo por 90 dias.

Robôs de busca e de pré-visualização de link (o Facebook abre o link toda vez
que alguém compartilha) são gravados com a marca `robo` e **ficam fora de todos
os números** do painel.

### As suas próprias visitas

Quem cuida do site entra nele o tempo todo, e isso viraria movimento falso. Por
isso **entrar no painel marca aquele aparelho**: dali em diante o que você abrir
no site por ali é gravado com a marca `interno` e fica fora das contas, do mesmo
jeito que os robôs.

A marca é um cookie, então vale por aparelho e por navegador, e dura dois anos.
Se você usa celular e computador, entre no painel pelos dois. No fim do painel,
na seção "Suas próprias visitas", dá para desligar (útil se você entrou no
computador de outra pessoa) e ligar de novo.

É uma chave só, o cookie — estar logado não conta por si. Se contasse, quem
clicasse em "voltar a contar" continuaria fora dos números até a sessão expirar,
e o botão pareceria quebrado.

### O que é guardado

Cada visita guarda: data e hora, um número aleatório de visitante (cookie, só
para separar "visitas" de "pessoas"), a origem, o aparelho, o navegador, o
endereço IP, quanto da página foi vista e por quantos segundos. Sem nome, sem
e-mail, sem rastreador de terceiros — nenhum dado sai do servidor.

O IP é o único campo que a LGPD trata como dado pessoal. Ele não é usado em
nenhum número do painel; está ali para investigar abuso. Se não fizer falta,
apagá-lo do `models.py` deixa a base inteiramente anônima.

### Cliques

Os botões marcados com `data-evento` no `templates/landing/index.html` avisam o
servidor quando são clicados. Para acrescentar um botão novo ao relatório:

1. registre o código e o nome em `EVENTOS`, no `painel/models.py`;
2. ponha `data-evento="o_codigo"` no `<a>` ou `<button>`.

Só códigos que estão nessa lista são aceitos — o endereço `/evento/` ignora
qualquer outra coisa.

Os códigos em `EVENTOS_WHATSAPP` são os que contam como conversão: hoje o botão
flutuante, o do topo, o do fim da página e o principal da primeira tela
(`diagnostico`) — os quatro abrem a mesma conversa. "Ver o que fazemos" e os itens
de menu ficam fora: são interesse, não conversa.

A conversão é decidida na leitura do relatório, não na gravação do clique. Então
acrescentar um código a `EVENTOS_WHATSAPP` **vale também para o histórico**: os
cliques que já estavam gravados passam a contar.

### A imagem do topo

O hero é servido em WebP por `<picture>`, em três larguras, com um JPEG de
reserva para navegador sem suporte. O original (`hero-automation.png`, 1,4 MB)
não é mais usado pela página — ficou no repositório só como fonte. Para gerar as
versões de novo depois de trocar a arte:

```powershell
.venv\Scripts\pip install Pillow
.venv\Scripts\python - <<'FIM'
from PIL import Image
from pathlib import Path
pasta = Path("static/landing/img")
im = Image.open(pasta / "hero-automation.png").convert("RGB")
for largura in (800, 1200, 1717):
    altura = round(im.height * largura / im.width)
    copia = im.resize((largura, altura), Image.LANCZOS)
    copia.save(pasta / f"hero-automation-{largura}.webp", "WEBP", quality=72, method=6)
altura = round(im.height * 1200 / im.width)
im.resize((1200, altura), Image.LANCZOS).save(
    pasta / "hero-automation-1200.jpg", "JPEG", quality=78, optimize=True, progressive=True)
FIM
```

O Pillow é ferramenta de edição de imagem, usada só nessa hora — por isso **não**
está no `requirements.txt`.

---

## Publicar

No seu computador:

```bash
git add .
git commit -m "Descrição do que mudou"
git push
```

No servidor, como root:

```bash
ssh vps
/var/www/polloniflow/deploy/deploy.sh
```

O script faz backup do banco, baixa o código, instala dependências, aplica as
migrações, recolhe os estáticos, recria o acesso ao painel se ele não existir,
reinicia o serviço e confere se o site respondeu — voltando tudo atrás sozinho
se algo falhar.

### O banco

O painel usa SQLite em `db.sqlite3`, que **fica fora do Git**. Ele é o único
lugar onde o histórico de visitas existe: o backup do `deploy.sh` (em
`/var/www/polloniflow/backup/`) mora na mesma máquina, então de tempos em tempos
vale trazer uma cópia para casa:

```bash
scp vps:/var/www/polloniflow/db.sqlite3 ./copia-do-banco.sqlite3
```

### Nginx

O site responde em `fabianopolone.com.br`, pelo arquivo
`/etc/nginx/sites-available/site_idiomas`, que também abriga os outros sistemas
em subpastas (`/trade/`, `/beezap/`, `/italiano/`…). O painel e o endereço
`/evento/` entram pelo `location /`, junto com a página — não precisa de
configuração nova.

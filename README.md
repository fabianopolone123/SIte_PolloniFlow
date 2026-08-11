# Site Polloni Flow

Landing page em Django para a empresa Polloni Flow, no ar em
<https://fabianopolone.com.br>.

O site tem duas partes:

- a **página** que o visitante vê (app `landing`);
- um **painel de relatórios** protegido por senha (app `painel`), que mostra de
  onde vieram as visitas e quantas viraram conversa no WhatsApp.

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
| Anúncio ou orgânico | Quanto do movimento veio de campanha paga e quanto veio sozinho — e qual dos dois converte melhor |
| Visitas por dia | O movimento ao longo do período, já separado entre anúncio e orgânico |
| De onde vieram | Anúncio, busca, redes sociais, outros sites, direto |
| Campanhas de anúncio | Uma linha por campanha e por criativo, com a conversão de cada um |
| Cliques nos botões | Quantas vezes cada botão da página foi clicado |
| Aparelhos | Celular, computador, tablet |
| Últimas visitas | As 25 mais recentes, uma a uma |

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

### O que é guardado

Nada que identifique a pessoa. Cada visita guarda: data e hora, um número
aleatório de visitante (cookie, só para separar "visitas" de "pessoas"), a
origem, o aparelho, o navegador e o endereço IP. Sem nome, sem e-mail, sem
rastreador de terceiros — nenhum dado sai do servidor.

### Cliques

Os botões marcados com `data-evento` no `templates/landing/index.html` avisam o
servidor quando são clicados. Para acrescentar um botão novo ao relatório:

1. registre o código e o nome em `EVENTOS`, no `painel/models.py`;
2. ponha `data-evento="o_codigo"` no `<a>` ou `<button>`.

Só códigos que estão nessa lista são aceitos — o endereço `/evento/` ignora
qualquer outra coisa.

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

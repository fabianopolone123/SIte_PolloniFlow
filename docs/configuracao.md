# Configuração

Toda a configuração está em
[polloniflow/settings.py](../polloniflow/settings.py) — um arquivo, sem
`settings/base.py` + `settings/prod.py`. A diferença entre desenvolvimento e
produção vem de **variáveis de ambiente**, não de arquivos separados.

## Variáveis de ambiente

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | `"dev-polloni-flow-static-page"` | Chave de assinatura de sessão e CSRF |
| `DJANGO_DEBUG` | `"False"` | Ligada só em desenvolvimento; comparada com `.lower() == "true"` |
| `DJANGO_DB_PATH` | `BASE_DIR / "db.sqlite3"` | Caminho do arquivo SQLite |

Três coisas a saber sobre esses padrões:

**`DJANGO_DEBUG` é `False` por padrão.** Errar para o lado seguro: esquecer a
variável em produção não expõe o site. Em troca, para desenvolver é preciso
lembrar de ligá-la.

**A `SECRET_KEY` tem um valor de desenvolvimento embutido.** Em produção,
`DJANGO_SECRET_KEY` **precisa** estar definida no ambiente do serviço (systemd na
VPS). Se não estiver, o site funciona — e é exatamente esse o risco: nenhuma
mensagem de erro avisa, mas as sessões passam a ser assinadas com uma chave
pública, presente neste repositório. Ao publicar, confira que a variável existe.

**Trocar a `SECRET_KEY` invalida todas as sessões**, e ninguém fica logado no
painel. Só isso — nenhum dado se perde.

## `DEBUG` e o que ele muda

| Configuração | `DEBUG=True` | `DEBUG=False` |
| --- | --- | --- |
| `SESSION_COOKIE_SECURE` | `False` | `True` |
| `CSRF_COOKIE_SECURE` | `False` | `True` |
| Estáticos | Servidos pelo Django | Precisam de `collectstatic` + Nginx |
| Página de erro | Traceback completo | 500 padrão |

Os cookies seguros são escritos como `not DEBUG`, e é por isso que dá para entrar
no painel em `http://127.0.0.1:8000/` durante o desenvolvimento: com cookie
`Secure` num endereço HTTP, o navegador descartaria a sessão e o login pareceria
"não funcionar".

## Domínio

```python
ALLOWED_HOSTS = ["127.0.0.1", "localhost",
                 "fabianopolone.com.br", "www.fabianopolone.com.br"]

CSRF_TRUSTED_ORIGINS = ["https://fabianopolone.com.br",
                        "https://www.fabianopolone.com.br"]
```

`CSRF_TRUSTED_ORIGINS` é obrigatório aqui: o Django 4+ exige a origem completa
com esquema para aceitar POST vindo de HTTPS atrás de proxy. Sem ela, o login do
painel falharia com "CSRF verification failed".

**Ao trocar de domínio, são três lugares:** essas duas listas e a constante
`DOMINIO` em [painel/coleta.py](../painel/coleta.py) — que é o que impede o
próprio site de aparecer no relatório como site de origem.

## Apps instalados

```python
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "landing",
    "painel",
]
```

O que **não** está aqui é tão informativo quanto o que está:

- **sem `django.contrib.admin`** — não existe Django Admin neste projeto. O painel
  é a única interface, e o shell é a única forma de mexer em dado bruto.
- **sem `django.contrib.messages`** — os erros de formulário são strings passadas
  no contexto (veja `entrar` em [referencia-de-funcoes.md](referencia-de-funcoes.md)).
- **sem `django.contrib.humanize`** — a formatação é feita nos filtros padrão.

`auth` e `sessions` ficam porque o painel tem login. `contenttypes` é dependência
de `auth`.

O `MIDDLEWARE` é o padrão do Django, sem nada de terceiros e sem middleware
próprio — a coleta é chamada pela view, não por middleware, pelo motivo explicado
em [arquitetura.md](arquitetura.md#decisões-de-arquitetura-e-o-motivo).

## Templates

```python
"DIRS": [BASE_DIR / "templates"],
"APP_DIRS": True,
```

Os `context_processors` são apenas dois: `request` e `auth`. O de `request` é o
que dá `{{ request }}` e permite `{% url %}` com resolução de esquema; o de `auth`
é o que dá `{{ user.username }}` no topo do painel.

## Localização

```python
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
```

`USE_TZ = True` significa que o banco guarda UTC e o Django converte na
exibição. É por isso que [relatorio.py](../painel/relatorio.py) usa
`timezone.localdate()` e `timezone.make_aware(...)` — sem isso, "hoje" seria o dia
em UTC e as visitas do fim da noite cairiam no dia seguinte.

`LANGUAGE_CODE = "pt-br"` é a causa da necessidade de `|unlocalize` nos templates
do painel; veja [frontend.md](frontend.md#gráficos-sem-biblioteca).

## Arquivos estáticos

```python
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
```

`STATICFILES_DIRS` é a origem (versionada); `STATIC_ROOT` é o destino do
`collectstatic`, ignorado pelo Git e servido pelo Nginx.

## Banco

```python
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
}}
```

SQLite, com o caminho configurável. O comentário no arquivo é o essencial: **o
banco fica fora do Git porque é dado de produção, não código.** Veja
[deploy.md](deploy.md#o-banco-é-o-ativo).

## Proxy e HTTPS

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

O site roda atrás do Nginx, que termina o HTTPS e repassa o esquema original neste
cabeçalho. Sem essa linha, o Django acharia que toda visita chegou por HTTP e não
marcaria os cookies como seguros — e `request.is_secure()`, usado por
`aplicar_cookies`, devolveria `False` sempre.

Essa configuração **exige** que o Nginx sempre defina `X-Forwarded-Proto`. Se um
dia o Django ficar exposto direto na internet, ela precisa sair: um cliente
poderia mandar o cabeçalho na mão e o Django acreditaria.

## Sessão e login

```python
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12      # 12 horas
CSRF_COOKIE_SECURE = not DEBUG

LOGIN_URL = "/painel/entrar/"
LOGIN_REDIRECT_URL = "/painel/"
LOGOUT_REDIRECT_URL = "/painel/entrar/"
```

A sessão dura 12 horas — curta o suficiente para não deixar o painel aberto
indefinidamente num aparelho compartilhado. Não confunda com o cookie
`pf_interno`, que dura dois anos e **não** depende de sessão: expirar a sessão não
faz suas visitas voltarem a contar. Isso é deliberado, e o motivo está em
[coleta-de-dados.md](coleta-de-dados.md#as-visitas-do-dono-do-site).

`LOGIN_URL` é o que o decorador `@login_required` usa para redirecionar.

## O que não está configurado, e vale saber

| Configuração | Situação | Comentário |
| --- | --- | --- |
| `SECURE_SSL_REDIRECT` | ausente | O redirecionamento HTTP→HTTPS é feito pelo Nginx |
| `SECURE_HSTS_SECONDS` | ausente | HSTS, se existir, está no Nginx |
| `LOGGING` | ausente | Usa o padrão do Django; `registro.exception` de `coleta.py` sai no log do gunicorn/systemd |
| `AUTH_PASSWORD_VALIDATORS` | ausente | O acesso é criado por `set_password` no comando, que não passa por validador de qualquer forma |
| `DEFAULT_AUTO_FIELD` | `BigAutoField` | Também repetido em `painel/apps.py` |

A ausência de `LOGGING` é a mais relevante no dia a dia: quando uma visita não é
registrada, a exceção existe — ela está no journal do serviço, não em arquivo do
projeto (`journalctl -u <serviço> -n 100`).

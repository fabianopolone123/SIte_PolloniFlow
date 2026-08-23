# Publicação

> As informações desta página sobre a VPS (caminhos, script de deploy, arquivo do
> Nginx) vêm do [README.md](../README.md) do projeto — a infraestrutura não está
> neste repositório. O que está aqui é o que o repositório precisa que seja
> verdade no servidor.

## O fluxo

No seu computador:

```powershell
git add .
git commit -m "Descrição do que mudou"
git push
```

No servidor, como root:

```bash
ssh vps
/var/www/polloniflow/deploy/deploy.sh
```

O script faz, em ordem: backup do banco, baixa o código, instala dependências,
aplica as migrações, recolhe os estáticos, recria o acesso ao painel se ele não
existir, reinicia o serviço e confere se o site respondeu — voltando tudo atrás
sozinho se algo falhar.

O passo "recria o acesso ao painel se ele não existir" é seguro em toda publicação
justamente porque `criar_painel` **preserva a senha de um acesso existente** sem
`--trocar-senha`. Veja
[referencia-de-funcoes.md](referencia-de-funcoes.md#painelmanagementcommandscriar_painelpy).

## O que o servidor precisa fornecer

Estas são as dependências do código sobre o ambiente. Se alguma faltar, o site
funciona mas alguma coisa fica errada — e nenhuma delas dá mensagem de erro.

| Requisito | Se faltar |
| --- | --- |
| `DJANGO_SECRET_KEY` no ambiente do serviço | As sessões passam a ser assinadas com a chave de desenvolvimento, que está neste repositório |
| `DJANGO_DEBUG` ausente ou diferente de `true` | Traceback exposto ao público |
| Nginx definindo `X-Forwarded-Proto` | O Django acha que tudo chegou por HTTP e não marca os cookies como `Secure` |
| Nginx repassando `X-Real-IP` ou `X-Forwarded-For` | O campo `ip` de toda visita fica sendo o do próprio servidor |
| `collectstatic` rodado | Página sem CSS, sem JS, sem as imagens do hero — e, sem JS, sem clique nem medida de leitura |
| Permissão de escrita no diretório do `db.sqlite3` | Nenhuma visita é registrada (o erro vai só para o log) |

O SQLite precisa de escrita **no diretório**, não só no arquivo — ele cria o
`-wal` e o `-journal` ao lado.

## Nginx

O site responde em `fabianopolone.com.br`, pelo arquivo
`/etc/nginx/sites-available/site_idiomas`, que também abriga outros sistemas em
subpastas (`/trade/`, `/beezap/`, `/italiano/`…).

O painel e a rota `/evento/` entram pelo `location /`, junto com a página — **não
precisam de configuração nova**. Uma rota nova acrescentada em
[painel/urls.py](../painel/urls.py) também não precisará, desde que não colida com
uma dessas subpastas.

O Nginx é quem termina o HTTPS e quem faz o redirecionamento HTTP→HTTPS; o Django
não tem `SECURE_SSL_REDIRECT`.

## O banco é o ativo

`db.sqlite3` **fica fora do Git** (`*.sqlite3` no
[.gitignore](../.gitignore) — confirmado: o arquivo não está rastreado). Isso é
correto, e tem uma consequência que precisa ser dita com clareza:

**O banco de produção é o único lugar onde o histórico de visitas existe.** Não há
cópia no repositório, não há réplica, não há exportação automática para fora da
máquina. O backup que o `deploy.sh` faz (em `/var/www/polloniflow/backup/`) mora
**na mesma VPS** — protege contra migração ruim, não contra perda da máquina.

Por isso, de tempos em tempos, traga uma cópia para casa:

```bash
scp vps:/var/www/polloniflow/db.sqlite3 ./copia-do-banco.sqlite3
```

Vale como rotina mensal. Se o volume do site crescer o suficiente para o relatório
importar de verdade, os dois próximos passos naturais são um backup para fora da
máquina e a troca do SQLite por Postgres.

## Depois de publicar, confira

1. A página abre em <https://fabianopolone.com.br> com CSS e a animação de fundo.
2. O painel abre em `/painel/` e pede login.
3. Uma visita nova aparece em "Últimas visitas" — abra o site de um aparelho
   **não** marcado como interno (celular no 4G, por exemplo), ou os números não vão
   se mover.
4. Um clique no botão do WhatsApp aparece no bloco "Cliques nos botões".
5. O bloco "Quanto leram e quanto tempo ficaram" mostra cobertura acima de 0% —
   é o que confirma que `/medida/` está recebendo os avisos do navegador. Feche a
   aba do site antes de conferir: o aviso é enviado na saída.

O passo 3 é o que mais confunde: no seu computador de trabalho, o cookie
`pf_interno` está ligado, e toda visita sua é gravada fora das contas — de
propósito. O bloco "Suas próprias visitas", no fim do painel, mostra o estado
daquele aparelho.

## Se algo der errado

```bash
# O que o serviço registrou
journalctl -u <nome-do-serviço> -n 100 --no-pager

# Configuração do Nginx e recarga
nginx -t && systemctl reload nginx
```

O projeto não configura `LOGGING`, então tudo — inclusive o
`registro.exception` de falha ao registrar visita — sai no journal do serviço.
Veja [configuracao.md](configuracao.md#o-que-não-está-configurado-e-vale-saber).

Erros de medição são silenciosos por decisão de projeto: a página nunca quebra por
causa do painel. O preço é que uma falha de gravação só aparece no log, nunca na
tela.

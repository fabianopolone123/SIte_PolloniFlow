# Documentação do Site Polloni Flow

Esta pasta descreve o projeto por inteiro: o que ele é, como está montado, o que
cada arquivo e cada função fazem, e como mexer nele sem quebrar os relatórios.

O [README.md](../README.md) na raiz é o guia curto de operação — como rodar, como
publicar, como trocar a senha do painel. Estes documentos são a explicação longa:
o *porquê* de cada decisão e a referência de código.

## Os documentos

| Documento | O que responde |
| --- | --- |
| [visao-geral.md](visao-geral.md) | O que é o projeto, para quem, com que tecnologia, e o vocabulário usado no código |
| [arquitetura.md](arquitetura.md) | Estrutura de pastas, as rotas do sistema, o caminho de uma requisição de ponta a ponta |
| [modelo-de-dados.md](modelo-de-dados.md) | Tabelas `Visita` e `Clique`, campo por campo, e as migrações |
| [coleta-de-dados.md](coleta-de-dados.md) | Como uma visita é registrada e como o canal de origem é decidido; cookies, robôs e visitas do dono |
| [medicao-de-leitura.md](medicao-de-leitura.md) | Rolagem e tempo de permanência: como são medidos, o teto, a cobertura e por que a mediana |
| [relatorio.md](relatorio.md) | Cada bloco do painel e a conta exata por trás de cada número |
| [referencia-de-funcoes.md](referencia-de-funcoes.md) | Catálogo de todas as funções, classes e constantes do projeto |
| [frontend.md](frontend.md) | A landing page, os templates do painel, o CSS e o JavaScript |
| [configuracao.md](configuracao.md) | `settings.py` linha a linha, variáveis de ambiente e as decisões de segurança |
| [desenvolvimento.md](desenvolvimento.md) | Rodar local, a suíte de testes, comandos e receitas de alteração |
| [deploy.md](deploy.md) | Publicação, Nginx, o banco de produção e o backup |

## Leitura recomendada por objetivo

- **Chegou agora no projeto:** [visao-geral.md](visao-geral.md) → [arquitetura.md](arquitetura.md) → [modelo-de-dados.md](modelo-de-dados.md)
- **Vai mexer na página:** [frontend.md](frontend.md) → a receita "acrescentar um botão medido" em [desenvolvimento.md](desenvolvimento.md)
- **Um número do painel parece errado:** [relatorio.md](relatorio.md) → [coleta-de-dados.md](coleta-de-dados.md) → [medicao-de-leitura.md](medicao-de-leitura.md)
- **Vai publicar:** [deploy.md](deploy.md) → [configuracao.md](configuracao.md)

## Estado verificado

Levantado em 22/08/2026, com o código no commit `9673f42`:

- Django 5.2.17, Python 3.13
- `manage.py test painel` → **49 testes, todos passando**
- Três migrações aplicadas em `painel`; os apps `landing` e `polloniflow` não têm modelos
- Oito eventos medidos, três deles contando como conversão

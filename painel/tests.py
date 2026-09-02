from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from django.core.management import call_command

from . import relatorio
from .coleta import COOKIE_INTERNO, COOKIE_ORIGEM, COOKIE_VISITANTE
from .models import Canal, Clique, Dispositivo, Visita

CELULAR = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605 Version/17 Mobile Safari/604"
COMPUTADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36"


class ClassificacaoDaOrigem(TestCase):
    """A pergunta central do painel: esta visita veio de anúncio ou não?"""

    def visitar(self, endereco="/", **cabecalhos):
        cabecalhos.setdefault("HTTP_USER_AGENT", CELULAR)
        self.client.get(endereco, **cabecalhos)
        return Visita.objects.latest("id")

    def test_utm_de_campanha_paga_vira_anuncio(self):
        visita = self.visitar("/?utm_source=ig&utm_medium=paid&utm_campaign=Agosto")
        self.assertEqual(visita.canal, Canal.ANUNCIO)
        self.assertEqual(visita.campanha, "Agosto")
        self.assertEqual(visita.origem, "ig")

    def test_identificador_de_clique_do_facebook_vira_anuncio(self):
        # É o caso real do anúncio do Instagram: chega só com o fbclid.
        self.assertEqual(self.visitar("/?fbclid=abc123").canal, Canal.ANUNCIO)

    def test_google_ads_vira_anuncio(self):
        self.assertEqual(self.visitar("/?gclid=xyz").canal, Canal.ANUNCIO)

    def test_busca_no_google_vira_organico(self):
        visita = self.visitar("/", HTTP_REFERER="https://www.google.com/search?q=automacao")
        self.assertEqual(visita.canal, Canal.BUSCA)
        self.assertEqual(visita.origem, "www.google.com")

    def test_link_do_instagram_sem_pagar_vira_rede_social(self):
        visita = self.visitar("/", HTTP_REFERER="https://l.instagram.com/")
        self.assertEqual(visita.canal, Canal.SOCIAL)

    def test_outro_site_vira_referencia(self):
        visita = self.visitar("/", HTTP_REFERER="https://pinhaljunior.com.br/parceiros")
        self.assertEqual(visita.canal, Canal.REFERENCIA)

    def test_sem_pista_nenhuma_vira_direto(self):
        self.assertEqual(self.visitar("/").canal, Canal.DIRETO)

    def test_link_dentro_do_proprio_site_nao_conta_como_origem(self):
        visita = self.visitar("/", HTTP_REFERER="https://fabianopolone.com.br/")
        self.assertEqual(visita.canal, Canal.DIRETO)
        self.assertEqual(visita.referencia, "")

    def test_campanha_continua_valendo_na_segunda_visita(self):
        primeira = self.visitar("/?utm_source=ig&utm_medium=paid&utm_campaign=Agosto")
        segunda = self.visitar("/")
        self.assertEqual(segunda.canal, Canal.ANUNCIO)
        self.assertEqual(segunda.campanha, "Agosto")
        # E é a mesma pessoa: uma visita a mais, não um visitante a mais.
        self.assertEqual(primeira.visitante, segunda.visitante)

    def test_cookie_de_origem_adulterado_e_ignorado(self):
        self.client.cookies[COOKIE_ORIGEM] = "canal=invadido&campanha=x"
        self.assertEqual(self.visitar("/").canal, Canal.DIRETO)

    def test_robo_e_marcado_e_nao_atrapalha_a_contagem(self):
        visita = self.visitar("/", HTTP_USER_AGENT="facebookexternalhit/1.1")
        self.assertTrue(visita.robo)

    def test_aparelho_sai_do_navegador(self):
        self.assertEqual(self.visitar("/").dispositivo, Dispositivo.CELULAR)
        self.assertEqual(
            self.visitar("/", HTTP_USER_AGENT=COMPUTADOR).dispositivo, Dispositivo.COMPUTADOR
        )


class RegistroDeCliques(TestCase):
    def setUp(self):
        self.client.get("/?utm_medium=cpc&utm_campaign=Agosto", HTTP_USER_AGENT=CELULAR)
        self.visita = Visita.objects.latest("id")

    def avisar(self, **dados):
        return self.client.post(reverse("evento"), dados)

    def test_clique_valido_e_gravado_com_o_canal_da_visita(self):
        self.assertEqual(self.avisar(evento="whatsapp_topo", visita=self.visita.pk).status_code, 204)
        clique = Clique.objects.get()
        self.assertEqual(clique.evento, "whatsapp_topo")
        self.assertEqual(clique.canal, Canal.ANUNCIO)

    def test_botao_inventado_nao_e_gravado(self):
        self.avisar(evento="qualquer_coisa", visita=self.visita.pk)
        self.assertEqual(Clique.objects.count(), 0)

    def test_clique_de_outra_pessoa_nao_e_gravado(self):
        self.client.cookies[COOKIE_VISITANTE] = "0" * 32
        self.avisar(evento="whatsapp_topo", visita=self.visita.pk)
        self.assertEqual(Clique.objects.count(), 0)

    def test_visita_inexistente_nao_derruba_o_endereco(self):
        self.assertEqual(self.avisar(evento="whatsapp_topo", visita="999999").status_code, 204)
        self.assertEqual(Clique.objects.count(), 0)


class MedidaDeLeitura(TestCase):
    """O aviso de quanto a pessoa leu e por quanto tempo ficou."""

    def setUp(self):
        self.client.get("/?utm_medium=cpc", HTTP_USER_AGENT=CELULAR)
        self.visita = Visita.objects.latest("id")

    def medir(self, cliente=None, **dados):
        dados.setdefault("visita", self.visita.pk)
        return (cliente or self.client).post(reverse("medida"), dados)

    def recarregar(self):
        self.visita.refresh_from_db()
        return self.visita

    def test_grava_rolagem_e_tempo(self):
        self.assertEqual(self.medir(rolagem=64, segundos=45).status_code, 204)
        visita = self.recarregar()
        self.assertTrue(visita.medido)
        self.assertEqual(visita.rolagem, 64)
        self.assertEqual(visita.segundos, 45)

    def test_visita_nasce_sem_medida(self):
        self.assertFalse(self.visita.medido)
        self.assertEqual(self.visita.rolagem, 0)

    def test_segundo_aviso_menor_nao_apaga_o_maior(self):
        # Quem volta para a aba e sai de novo manda outro aviso. O maior vale.
        self.medir(rolagem=90, segundos=120)
        self.medir(rolagem=12, segundos=3)
        visita = self.recarregar()
        self.assertEqual(visita.rolagem, 90)
        self.assertEqual(visita.segundos, 120)

    def test_aviso_maior_substitui_o_anterior(self):
        self.medir(rolagem=30, segundos=10)
        self.medir(rolagem=100, segundos=200)
        visita = self.recarregar()
        self.assertEqual(visita.rolagem, 100)
        self.assertEqual(visita.segundos, 200)

    def test_valores_absurdos_sao_aparados(self):
        self.medir(rolagem=8000, segundos=999999)
        visita = self.recarregar()
        self.assertEqual(visita.rolagem, 100)
        self.assertEqual(visita.segundos, 30 * 60)

    def test_valor_sem_sentido_nao_derruba_o_endereco(self):
        self.assertEqual(self.medir(rolagem="abc", segundos="").status_code, 204)
        self.assertEqual(self.recarregar().rolagem, 0)

    def test_medida_de_outra_pessoa_e_ignorada(self):
        estranho = Client()
        estranho.cookies[COOKIE_VISITANTE] = "0" * 32
        self.medir(estranho, rolagem=100, segundos=300)
        visita = self.recarregar()
        self.assertFalse(visita.medido)
        self.assertEqual(visita.rolagem, 0)

    def test_visita_inexistente_nao_derruba_o_endereco(self):
        resposta = self.client.post(
            reverse("medida"), {"visita": "999999", "rolagem": 50, "segundos": 20}
        )
        self.assertEqual(resposta.status_code, 204)


class RelatorioDeEngajamento(TestCase):
    """Os números que respondem 'leram a página e mesmo assim não chamaram?'."""

    def visita(self, **campos):
        campos.setdefault("visitante", uuid4().hex)
        campos.setdefault("canal", Canal.ANUNCIO)
        return Visita.objects.create(**campos)

    def test_conta_quem_rolou_ate_o_fim(self):
        self.visita(medido=True, rolagem=95, segundos=60)
        self.visita(medido=True, rolagem=100, segundos=90)
        self.visita(medido=True, rolagem=18, segundos=4)
        self.visita(medido=True, rolagem=50, segundos=30)

        dados = relatorio.montar(30)["engajamento"]
        self.assertEqual(dados["medidas"], 4)
        self.assertEqual(dados["ate_o_fim"], 50.0)
        self.assertEqual(dados["so_o_topo"], 25.0)
        self.assertEqual(dados["saida_rapida"], 25.0)

    def test_tempo_tipico_usa_a_mediana(self):
        for segundos in (5, 10, 20, 30, 600):
            self.visita(medido=True, rolagem=40, segundos=segundos)

        dados = relatorio.montar(30)["engajamento"]
        # A aba esquecida aberta (600s) puxa a média, mas não a mediana.
        self.assertEqual(dados["tempo_mediano"], 20)
        self.assertEqual(dados["tempo_mediano_texto"], "20s")
        self.assertEqual(dados["tempo_medio"], 133)

    def test_tempo_longo_vira_minutos(self):
        for _ in range(3):
            self.visita(medido=True, rolagem=80, segundos=200)
        dados = relatorio.montar(30)["engajamento"]
        self.assertEqual(dados["tempo_mediano_texto"], "3min 20s")

    def test_visita_nao_medida_fica_fora_das_medias(self):
        """O ponto: visita antiga não pode virar abandono que ninguém viu."""
        self.visita(medido=True, rolagem=100, segundos=120)
        self.visita()  # sem medida — anterior à medição existir
        self.visita()

        dados = relatorio.montar(30)["engajamento"]
        self.assertEqual(dados["medidas"], 1)
        self.assertEqual(dados["total"], 3)
        self.assertEqual(dados["ate_o_fim"], 100.0)
        self.assertAlmostEqual(dados["cobertura"], 33.3, places=1)

    def test_periodo_sem_medida_nenhuma_nao_quebra(self):
        self.visita()
        dados = relatorio.montar(30)["engajamento"]
        self.assertEqual(dados["medidas"], 0)
        self.assertEqual(dados["ate_o_fim"], 0.0)
        self.assertEqual(dados["tempo_mediano_texto"], "—")

    def test_robo_e_visita_interna_ficam_de_fora(self):
        self.visita(medido=True, rolagem=100, segundos=200, robo=True)
        self.visita(medido=True, rolagem=100, segundos=200, interno=True)
        self.assertEqual(relatorio.montar(30)["engajamento"]["medidas"], 0)

    def test_distribuicao_soma_as_visitas_medidas(self):
        for rolagem in (10, 30, 60, 80, 100):
            self.visita(medido=True, rolagem=rolagem, segundos=15)
        faixas = relatorio.montar(30)["engajamento"]["faixas_rolagem"]
        self.assertEqual(sum(linha["total"] for linha in faixas), 5)
        self.assertEqual([linha["total"] for linha in faixas], [1, 1, 1, 2])

    def test_anuncio_e_organico_trazem_o_proprio_engajamento(self):
        self.visita(canal=Canal.ANUNCIO, medido=True, rolagem=15, segundos=6)
        self.visita(canal=Canal.DIRETO, medido=True, rolagem=100, segundos=180)

        comparativo = relatorio.montar(30)["comparativo"]
        self.assertEqual(comparativo["anuncio"]["ate_o_fim"], 0.0)
        self.assertEqual(comparativo["organico"]["ate_o_fim"], 100.0)
        self.assertEqual(comparativo["organico"]["tempo_mediano_texto"], "3min")


class BotaoFlutuante(TestCase):
    """O atalho para a conversa que acompanha a rolagem."""

    def test_a_pagina_traz_o_botao_flutuante(self):
        resposta = self.client.get("/", HTTP_USER_AGENT=CELULAR)
        self.assertContains(resposta, 'class="whatsapp-flutuante"')
        self.assertContains(resposta, 'data-evento="whatsapp_flutuante"')
        self.assertContains(resposta, "wa.me/5514988208134")

    def test_o_clique_no_botao_flutuante_conta_como_whatsapp(self):
        self.client.get("/?fbclid=abc", HTTP_USER_AGENT=CELULAR)
        visita = Visita.objects.latest("id")
        self.client.post(
            reverse("evento"), {"evento": "whatsapp_flutuante", "visita": visita.pk}
        )
        self.assertEqual(Clique.objects.count(), 1)
        self.assertEqual(relatorio.montar(30)["resumo"]["cliques"], 1)

    def test_a_pagina_avisa_o_endereco_da_medicao(self):
        resposta = self.client.get("/", HTTP_USER_AGENT=CELULAR)
        self.assertContains(resposta, 'data-medida-url="/medida/"')


class ConversaoContaTodoBotaoQueAbreConversa(TestCase):
    """Botão que leva ao WhatsApp conta como conversa; o resto, não.

    O `diagnostico` é o botão principal da primeira tela e vai para a mesma
    conversa dos outros. Ficou fora da conta por um tempo, e a conversão do
    painel saía menor do que a real justamente no botão mais visível da página.
    """

    def clicar(self, codigo):
        self.client.get("/", HTTP_USER_AGENT=CELULAR)
        visita = Visita.objects.latest("id")
        self.client.post(reverse("evento"), {"evento": codigo, "visita": visita.pk})
        return relatorio.montar(30)["resumo"]["cliques"]

    def test_o_botao_principal_do_topo_conta(self):
        self.assertEqual(self.clicar("diagnostico"), 1)

    def test_o_botao_do_hero_aponta_mesmo_para_a_conversa(self):
        pagina = self.client.get("/", HTTP_USER_AGENT=CELULAR).content.decode()
        antes, _, depois = pagina.partition('data-evento="diagnostico"')
        # O href fica antes do data-evento, na mesma marcação.
        self.assertIn("wa.me/5514988208134", antes.rsplit("<a ", 1)[-1])

    def test_quem_nao_abre_conversa_nao_conta(self):
        nao_conversam = (
            "ver_solucoes",
            "menu_solucoes",
            "menu_processo",
            "menu_contato",
            "menu_portfolio",
            "projeto_samela",
            "projeto_pinhal",
            "projeto_esperanca",
            "projeto_italiano",
            "projeto_briefing",
            "projeto_trade",
        )
        for codigo in nao_conversam:
            with self.subTest(codigo=codigo):
                self.assertEqual(self.clicar(codigo), 0)


class Portfolio(TestCase):
    """Os trabalhos entregues, e o que a página promete sobre eles.

    Card sem link é decisão: o projeto roda na rede do cliente ou no celular,
    e não existe endereço público. Estes testes travam o contrário — que todo
    link que a página mostra leve mesmo para um site no ar, e que nenhum leve
    para repositório, porque o público daqui é dono de empresa.
    """

    NO_AR = {
        "projeto_samela": "https://samelapolloni.com.br",
        "projeto_pinhal": "https://pinhaljunior.com.br",
        "projeto_esperanca": "https://advministerioesperanca.com.br",
        "projeto_italiano": "https://fabianopolone.com.br/italiano",
        "projeto_briefing": "https://fabianopolone.com.br/desenvolvimento",
        "projeto_trade": "https://fabianopolone.com.br/TreinarTrade/",
    }

    def setUp(self):
        self.pagina = self.client.get("/", HTTP_USER_AGENT=CELULAR).content.decode()

    def test_a_secao_esta_na_pagina(self):
        self.assertIn('id="portfolio"', self.pagina)
        self.assertEqual(self.pagina.count('class="portfolio-card"'), 6)

    def test_todo_cartao_mostra_a_stack_e_leva_a_um_site(self):
        """Cartão sem link ou sem etiqueta de stack não entra na página.

        São as duas coisas que o cartão precisa entregar: a prova (o site no ar)
        e a informação (a tecnologia usada). Um cartão que perde uma das duas
        vira texto de propaganda.
        """
        self.assertEqual(self.pagina.count('class="portfolio-stack"'), 6)
        self.assertEqual(self.pagina.count('class="portfolio-link"'), 6)

    def test_o_menu_leva_ate_os_trabalhos(self):
        self.assertIn('href="#portfolio" data-evento="menu_portfolio"', self.pagina)

    def test_cada_projeto_com_link_aponta_para_o_site_no_ar(self):
        for codigo, endereco in self.NO_AR.items():
            with self.subTest(codigo=codigo):
                antes, _, _ = self.pagina.partition(f'data-evento="{codigo}"')
                self.assertIn(endereco, antes.rsplit("<a ", 1)[-1])

    def test_nenhum_projeto_manda_o_visitante_para_o_github(self):
        self.assertNotIn("github.com", self.pagina)

    def test_o_clique_no_projeto_e_gravado_sem_virar_conversa(self):
        self.client.get("/", HTTP_USER_AGENT=CELULAR)
        visita = Visita.objects.latest("id")
        for codigo in self.NO_AR:
            self.client.post(reverse("evento"), {"evento": codigo, "visita": visita.pk})
        resumo = relatorio.montar(30)["resumo"]
        self.assertEqual(Clique.objects.count(), len(self.NO_AR))
        self.assertEqual(resumo["cliques"], 0)


class PaginaLimpa(TestCase):
    def test_nenhum_comentario_vaza_para_a_pagina(self):
        """`{# #}` no Django vale para uma linha só.

        Escrito em várias linhas, ele deixa de ser comentário e o texto aparece
        na página, à vista do visitante. Já aconteceu: uma anotação interna sobre
        onde pôr a foto foi parar em cima do botão do WhatsApp.
        """
        pagina = self.client.get("/", HTTP_USER_AGENT=CELULAR).content.decode()
        for marca in ("{#", "#}", "{% comment %}", "{% endcomment %}"):
            self.assertNotIn(marca, pagina, f"{marca} vazou para a página")

    def test_a_faixa_nao_promete_numero_que_ninguem_mediu(self):
        pagina = self.client.get("/", HTTP_USER_AGENT=CELULAR).content.decode()
        self.assertNotIn("-80%", pagina)
        self.assertIn("Perguntar é de graça", pagina)

    def test_o_rosto_de_quem_responde_esta_na_pagina(self):
        pagina = self.client.get("/", HTTP_USER_AGENT=CELULAR).content.decode()
        self.assertIn("fabiano-112.webp", pagina)
        self.assertIn("fabiano-224.webp", pagina)  # tela retina
        self.assertIn("fabiano-112.jpg", pagina)  # navegador sem WebP
        self.assertIn('alt="Fabiano Polone"', pagina)


class AcessoAoPainel(TestCase):
    def setUp(self):
        call_command("criar_painel", verbosity=0)

    def test_painel_exige_entrar(self):
        resposta = Client().get("/painel/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/painel/entrar/", resposta["Location"])

    def test_entra_com_o_acesso_criado_pelo_comando(self):
        resposta = self.client.post(
            "/painel/entrar/", {"usuario": "fabiano", "senha": "1234"}, follow=True
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Resumo do período")

    def test_senha_errada_nao_entra(self):
        resposta = Client().post("/painel/entrar/", {"usuario": "fabiano", "senha": "nao"})
        self.assertContains(resposta, "incorretos")


class VisitasDoDono(TestCase):
    """As visitas de quem cuida do site não podem virar número de cliente."""

    def setUp(self):
        call_command("criar_painel", verbosity=0)

    def visitar(self, cliente=None):
        (cliente or self.client).get("/", HTTP_USER_AGENT=CELULAR)
        return Visita.objects.latest("id")

    def entrar(self):
        self.client.post("/painel/entrar/", {"usuario": "fabiano", "senha": "1234"})

    def test_visita_de_quem_nao_entrou_conta_normalmente(self):
        self.assertFalse(self.visitar().interno)

    def test_entrar_no_painel_marca_o_aparelho(self):
        self.entrar()
        self.assertEqual(self.client.cookies[COOKIE_INTERNO].value, "1")

    def test_visita_do_aparelho_marcado_nao_conta(self):
        self.entrar()
        self.assertTrue(self.visitar().interno)

    def test_clique_do_aparelho_marcado_tambem_nao_conta(self):
        self.entrar()
        visita = self.visitar()
        self.client.post(reverse("evento"), {"evento": "whatsapp_topo", "visita": visita.pk})
        self.assertTrue(Clique.objects.get().interno)

    def test_visita_marcada_fica_fora_do_relatorio(self):
        from . import relatorio

        self.entrar()
        self.visitar()
        self.visitar()
        dados = relatorio.montar(30)
        self.assertEqual(dados["resumo"]["visitas"], 0)
        self.assertEqual(dados["resumo"]["internos"], 2)

    def test_da_para_voltar_a_contar_o_aparelho(self):
        self.entrar()
        self.client.post(reverse("contagem"), {"acao": "contar"})
        self.assertFalse(self.visitar().interno)

    def test_marcar_de_novo_depois_de_ter_desligado(self):
        self.entrar()
        self.client.post(reverse("contagem"), {"acao": "contar"})
        self.client.post(reverse("contagem"), {"acao": "ignorar"})
        self.assertTrue(self.visitar().interno)

    def test_visitante_qualquer_nao_consegue_mexer_na_contagem(self):
        resposta = Client().post(reverse("contagem"), {"acao": "ignorar"})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/painel/entrar/", resposta["Location"])

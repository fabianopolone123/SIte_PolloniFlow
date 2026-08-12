from django.test import Client, TestCase
from django.urls import reverse

from django.core.management import call_command

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

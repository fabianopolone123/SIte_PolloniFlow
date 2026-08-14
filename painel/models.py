from django.db import models


class Canal(models.TextChoices):
    """De onde a pessoa veio. É o eixo principal dos relatórios."""

    ANUNCIO = "anuncio", "Anúncio pago"
    BUSCA = "busca", "Busca orgânica"
    SOCIAL = "social", "Redes sociais"
    REFERENCIA = "referencia", "Outros sites"
    DIRETO = "direto", "Direto"


class Dispositivo(models.TextChoices):
    CELULAR = "celular", "Celular"
    TABLET = "tablet", "Tablet"
    COMPUTADOR = "computador", "Computador"


# Cada botão da página tem um código. Só estes são aceitos pelo registrador de
# cliques — assim ninguém consegue inventar evento novo mandando requisição na
# mão. A ordem aqui é a ordem em que aparecem no relatório.
EVENTOS = {
    "whatsapp_flutuante": "Botão flutuante do WhatsApp",
    "whatsapp_topo": "Falar agora (botão do topo)",
    "whatsapp_final": "Chamar no WhatsApp (final da página)",
    "diagnostico": "Solicitar diagnóstico",
    "ver_solucoes": "Ver soluções",
    "menu_solucoes": "Menu: Soluções",
    "menu_processo": "Menu: Processo",
    "menu_contato": "Menu: Contato",
}

# Os botões que levam para a conversa no WhatsApp. São eles que contam como
# "pessoa que chamou".
EVENTOS_WHATSAPP = ("whatsapp_flutuante", "whatsapp_topo", "whatsapp_final")


class Visita(models.Model):
    """Uma abertura da página inicial."""

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    # Identificador anônimo guardado num cookie, para separar "visitas"
    # (aberturas de página) de "pessoas" (visitantes diferentes).
    visitante = models.CharField(max_length=32, db_index=True)

    canal = models.CharField(
        max_length=20, choices=Canal.choices, default=Canal.DIRETO, db_index=True
    )
    origem = models.CharField(max_length=120, blank=True)
    midia = models.CharField(max_length=120, blank=True)
    campanha = models.CharField(max_length=180, blank=True)
    conteudo = models.CharField(max_length=180, blank=True)
    termo = models.CharField(max_length=180, blank=True)

    referencia = models.CharField(max_length=300, blank=True)
    caminho = models.CharField(max_length=300, blank=True)

    dispositivo = models.CharField(
        max_length=20, choices=Dispositivo.choices, default=Dispositivo.COMPUTADOR
    )
    agente = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    # Robôs de busca e de pré-visualização de link entram no site o tempo todo.
    # São gravados, mas ficam fora das contas do painel.
    robo = models.BooleanField(default=False, db_index=True)
    # Visita do próprio dono do site, reconhecida pelo aparelho. Também é
    # gravada e também fica fora das contas: quem mexe no site o dia inteiro
    # não pode aparecer no relatório como se fosse cliente.
    interno = models.BooleanField(default=False, db_index=True)

    # Engajamento, contado pelo navegador e enviado quando a pessoa sai da
    # página. Diz o que o clique sozinho não diz: quem leu a página inteira e
    # mesmo assim não chamou, e quem foi embora antes de ver qualquer coisa.
    #
    # `medido` separa "ficou 0 segundo" de "o navegador não chegou a contar" —
    # visitas gravadas antes desta medição existir, ou de quem saiu antes do
    # JavaScript rodar. Sem essa marca, toda visita antiga entraria nas médias
    # como se fosse um abandono imediato.
    medido = models.BooleanField(default=False, db_index=True)
    # Quanto da página a pessoa chegou a ver, de 0 a 100.
    rolagem = models.PositiveSmallIntegerField(default=0)
    # Segundos com a página à vista. Tempo de aba escondida não conta.
    segundos = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "visita"
        verbose_name_plural = "visitas"

    def __str__(self):
        return f"{self.get_canal_display()} em {self.criado_em:%d/%m/%Y %H:%M}"


class Clique(models.Model):
    """Um clique num botão da página."""

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    evento = models.CharField(max_length=40, db_index=True)
    visita = models.ForeignKey(
        Visita, related_name="cliques", null=True, blank=True, on_delete=models.SET_NULL
    )
    # Copiados da visita no momento do clique: assim o relatório por canal
    # continua correto mesmo se a visita for apagada numa limpeza futura.
    canal = models.CharField(
        max_length=20, choices=Canal.choices, default=Canal.DIRETO, db_index=True
    )
    robo = models.BooleanField(default=False, db_index=True)
    interno = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "clique"
        verbose_name_plural = "cliques"

    @property
    def rotulo(self):
        return EVENTOS.get(self.evento, self.evento)

    def __str__(self):
        return f"{self.rotulo} em {self.criado_em:%d/%m/%Y %H:%M}"

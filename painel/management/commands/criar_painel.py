from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria o acesso ao painel de relatórios, se ainda não existir."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", default="fabiano")
        parser.add_argument("--senha", default="1234")
        parser.add_argument(
            "--trocar-senha",
            action="store_true",
            help="Redefine a senha de um acesso que já existe.",
        )

    def handle(self, *args, **opcoes):
        Pessoa = get_user_model()
        pessoa, criada = Pessoa.objects.get_or_create(username=opcoes["usuario"])

        if criada or opcoes["trocar_senha"]:
            # set_password não passa pelos validadores de senha do Django, que
            # recusariam "1234". É de propósito: a senha aqui é escolhida por
            # quem roda o comando.
            pessoa.set_password(opcoes["senha"])
            pessoa.is_active = True
            pessoa.save()
            acao = "criado" if criada else "com a senha redefinida"
            self.stdout.write(self.style.SUCCESS(f"Acesso '{pessoa.username}' {acao}."))
        else:
            self.stdout.write(f"Acesso '{pessoa.username}' já existe; senha mantida.")

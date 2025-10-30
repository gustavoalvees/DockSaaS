import docker
import random
import logging
from database import Sqlite
from volume_manager import VolumeManager
import string
import os
logging.basicConfig(level=logging.INFO)

class ContainerManager:
    def __init__(self, volume, db):
        self.client = docker.from_env()
        self.db = db
        self.volumes = volume

    # ------------------------------------------------------
    # Gerar porta aleatória entre 30000 e 60000, evitando conflito
    # ------------------------------------------------------
    def _generate_port(self):
        existing_ports = [c["porta"] for c in self.db.list_containers()]
        while True:
            port = random.randint(30000, 60000)
            if port not in existing_ports:
                return port

    # ------------------------------------------------------
    # Criar container de banco de dados
    # ------------------------------------------------------
    def create_container(self, usuario: str, tipodb: str):
        tipodb = tipodb.lower()
        if tipodb not in ["mysql", "postgres"]:
            raise ValueError("tipodb deve ser 'mysql' ou 'postgres'")

        root_password = self.gerar_senha_embaralhada(usuario)

        # Buscar volume base do usuário
        user_volumes = [v for v in self.db.list_volumes() if v["usuario_responsavel"] == usuario]
        if not user_volumes:
            raise ValueError(f"Usuário {usuario} não possui volume registrado")
        volume = user_volumes[0]

        # 🔹 Criar subpasta única para este container
        subfolder_name = f"{tipodb}_{random.randint(1000, 9999)}"
        subfolder_path = os.path.join(volume["path"], subfolder_name)
        os.makedirs(subfolder_path, exist_ok=True)

        porta = self._generate_port()

        # 🔹 Configurar imagem e variáveis de ambiente
        if tipodb == "mysql":
            image = "mysql:8.0"
            env = {"MYSQL_ROOT_PASSWORD": root_password}
            bind_path = "/var/lib/mysql"
        else:
            image = "postgres:15"
            env = {"POSTGRES_PASSWORD": root_password}
            bind_path = "/var/lib/postgresql/data"

        try:
            container_name = f"{usuario}_{tipodb}_{random.randint(1000,9999)}"
            container = self.client.containers.run(
                image=image,
                name=container_name,
                environment=env,
                ports={f"{3306 if tipodb=='mysql' else 5432}/tcp": porta},
                volumes={subfolder_path: {"bind": bind_path, "mode": "rw"}},
                detach=True
            )

            # Registrar container no banco de dados
            self.db.add_container(container.id, usuario, tipodb, "root", root_password, porta)

            logging.info(f"✅ Container {container_name} criado para {usuario} ({tipodb}) na porta {porta}")
            logging.info(f"📁 Subpasta usada: {subfolder_path}")

            return {
                "container_name": container.name,
                "usuario": usuario,
                "tipodb": tipodb,
                "porta": porta,
                "volume": volume["name"],
                "path": subfolder_path
            }

        except Exception as e:
            logging.error(f"Erro ao criar container para {usuario}: {e}")
            raise

    # ------------------------------------------------------
    # Iniciar container
    # ------------------------------------------------------
    def start_container(self, container_id: str):
        try:
            info = self.db.get_container(container_id)
            if not info:
                raise ValueError("Container não encontrado no banco")
            container = self.client.containers.get(info["container_name"])
            container.start()
            logging.info(f"🚀 Container {container.name} iniciado com sucesso")
        except Exception as e:
            logging.error(f"Erro ao iniciar container {container_id}: {e}")
            raise

    # ------------------------------------------------------
    # Parar container
    # ------------------------------------------------------
    def stop_container(self, container_id: str):
        try:
            info = self.db.get_container(container_id)
            if not info:
                raise ValueError("Container não encontrado no banco")
            container = self.client.containers.get(info["container_name"])
            container.stop()
            logging.info(f"🛑 Container {container.name} parado com sucesso")
        except Exception as e:
            logging.error(f"Erro ao parar container {container_id}: {e}")
            raise

    # ------------------------------------------------------
    # Remover container (para exclusão total)
    # ------------------------------------------------------
    def remove_container(self, container_id: str):
        try:
            info = self.db.get_container(container_id)
            if not info:
                raise ValueError("Container não encontrado no banco")

            container = self.client.containers.get(info["container_name"])
            container.stop()
            container.remove()

            self.db.delete_container(container_id)
            logging.info(f"🗑️ Container {info['container_name']} removido com sucesso")
        except Exception as e:
            logging.error(f"Erro ao remover container {container_id}: {e}")
            raise

    # ------------------------------------------------------
    # Listar containers registrados no banco
    # ------------------------------------------------------
    def list_containers(self):
        return self.db.list_containers()

    # ------------------------------------------------------
    # Gerar uma senha com nome do usuario imbutido
    # ------------------------------------------------------
    def gerar_senha_embaralhada(self, nome: str) -> str:
        caracteres = string.ascii_letters + string.digits + "@#_*.lI;ç"
        tamanho_min = max(3, len(nome))
        tamanho_total = random.randint(tamanho_min, max(10, tamanho_min))
        aleatorios = random.choices(caracteres, k=tamanho_total)
        todos = list(nome) + aleatorios
        random.shuffle(todos)
        senha = ''.join(todos)
        return senha
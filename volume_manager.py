import docker
import subprocess
import os
import uuid
import logging
from database import Sqlite

logging.basicConfig(level=logging.INFO)


class VolumeManager:
    def __init__(self, base_dir="/var/lib/docker-imgs", db=None):
        self.client = docker.from_env()
        self.db = db
        self.base_dir = base_dir
        if(db == None):
            logging.error(f"Erro ao acesar banco de dados!")
        os.makedirs(self.base_dir, exist_ok=True)

    def _generate_volume_name(self, username: str) -> str:
        unique_id = str(uuid.uuid4())[:8]
        return f"{username}_{unique_id}"

    # ------------------------------------------------------
    # Criar volume baseado em .img (persistente e limitado)
    # ------------------------------------------------------
    def create_user_volume(self, username: str, limite_mb: int):
        volume_name = self._generate_volume_name(username)
        img_path = os.path.join(self.base_dir, f"{volume_name}.img")
        mount_path = f"/mnt/{volume_name}"

        try:
            subprocess.run(["fallocate", "-l", f"{limite_mb}M", img_path], check=True)
            subprocess.run(["mkfs.ext4", "-F", img_path], check=True)
            os.makedirs(mount_path, exist_ok=True)
            subprocess.run(["mount", "-o", "loop", img_path, mount_path], check=True)

            volume = self.client.volumes.create(
                name=volume_name,
                driver="local",
                driver_opts={"type": "none", "device": mount_path, "o": "bind"}
            )

            self.db.add_volume(volume_name, username, mount_path, limite_mb)
            logging.info(f"Volume .img criado para {username}: {volume_name} ({limite_mb}MB)")

            return {"name": volume_name, "path": mount_path, "limite_mb": limite_mb, "img_path": img_path}

        except Exception as e:
            logging.error(f"Erro ao criar volume .img para {username}: {e}")
            raise

    # ------------------------------------------------------
    # Incrementar espaço do volume
    # ------------------------------------------------------
    def increment_volume(self, volume_name: str, additional_mb: int):
        vol = self.db.get_volume(volume_name)
        if not vol:
            raise ValueError(f"Volume {volume_name} não encontrado")

        mount_path = vol["path"]
        img_path = os.path.join(self.base_dir, f"{volume_name}.img")

        try:
            # Desmontar o volume temporariamente
            subprocess.run(["umount", mount_path], check=True)

            # Aumentar tamanho do arquivo .img
            subprocess.run(["fallocate", "-l", f"+{additional_mb}M", img_path], check=True)

            # Verificar e reparar filesystem
            subprocess.run(["e2fsck", "-f", img_path], check=True)
            subprocess.run(["resize2fs", img_path], check=True)

            # Remontar
            subprocess.run(["mount", "-o", "loop", img_path, mount_path], check=True)

            # Atualizar limite no banco
            new_limit = vol["limite_mb"] + additional_mb
            self.db.update_volume_limit(volume_name, new_limit)
            logging.info(f"Volume '{volume_name}' aumentado em {additional_mb}MB. Novo limite: {new_limit}MB")

        except Exception as e:
            logging.error(f"Erro ao incrementar volume '{volume_name}': {e}")
            raise

    # ------------------------------------------------------
    # Consultar uso de espaço
    # ------------------------------------------------------
    def get_volume_usage(self, volume_name: str):
        vol = self.db.get_volume(volume_name)
        if not vol:
            raise ValueError(f"Volume {volume_name} não encontrado")

        try:
            result = subprocess.run(["df", "-m", vol["path"]], stdout=subprocess.PIPE, text=True, check=True)
            lines = result.stdout.splitlines()
            if len(lines) > 1:
                data = lines[1].split()
                usado_mb = int(data[2])
                total_mb = int(data[1])
                perc = data[4]
                return {"volume": volume_name, "used_mb": usado_mb, "total_mb": total_mb, "percent": perc}
            return {"volume": volume_name, "used_mb": 0, "total_mb": vol["limite_mb"], "percent": "0%"}
        except Exception as e:
            logging.error(f"Erro ao consultar volume '{volume_name}': {e}")
            raise

    # ------------------------------------------------------
    # Remover volume + desmontar .img
    # ------------------------------------------------------
    def delete_user_volumes(self, username: str):
        user_volumes = [v for v in self.db.list_volumes() if v["usuario_responsavel"] == username]

        for vol in user_volumes:
            mount_path = vol["path"]
            img_path = os.path.join(self.base_dir, f"{vol['name']}.img")
            try:
                docker_volume = self.client.volumes.get(vol["name"])
                docker_volume.remove(force=True)
                subprocess.run(["umount", mount_path], check=False)
                if os.path.exists(img_path): os.remove(img_path)
                if os.path.exists(mount_path): os.rmdir(mount_path)
                self.db.delete_volume(vol["name"])
                logging.info(f"Volume '{vol['name']}' removido com sucesso")
            except Exception as e:
                logging.warning(f"Erro ao remover volume '{vol['name']}': {e}")

    # ------------------------------------------------------
    # Hooks automáticos
    # ------------------------------------------------------
    def on_user_created(self, username: str):
        limite = self.db.get_user_limit(username) or 1024
        return self.create_user_volume(username, limite)

    def on_user_deleted(self, username: str):
        self.delete_user_volumes(username)
    # ------------------------------------------------------
    # Decrementar espaço do volume
    # ------------------------------------------------------
    def decrement_volume(self, volume_name: str, reduce_mb: int):
        vol = self.db.get_volume(volume_name)
        if not vol:
            raise ValueError(f"Volume {volume_name} não encontrado")

        mount_path = vol["path"]
        img_path = os.path.join(self.base_dir, f"{volume_name}.img")

        # 1️⃣ Consultar uso atual
        usage = self.get_volume_usage(volume_name)
        used_mb = usage["used_mb"]
        current_limit = vol["limite_mb"]
        new_limit = current_limit - reduce_mb

        if new_limit < used_mb:
            raise ValueError(f"Não é possível reduzir {reduce_mb}MB. Espaço usado: {used_mb}MB.")

        try:
            # 2️⃣ Desmontar
            subprocess.run(["umount", mount_path], check=True)

            # 3️⃣ Reduzir filesystem
            subprocess.run(["e2fsck", "-f", img_path], check=True)
            subprocess.run(["resize2fs", img_path, f"{new_limit}M"], check=True)

            # 4️⃣ Reduzir tamanho do arquivo .img
            subprocess.run(["truncate", "-s", f"{new_limit}M", img_path], check=True)

            # 5️⃣ Remontar
            subprocess.run(["mount", "-o", "loop", img_path, mount_path], check=True)

            # 6️⃣ Atualizar banco
            self.db.update_volume_limit(volume_name, new_limit)
            logging.info(f"Volume '{volume_name}' reduzido em {reduce_mb}MB. Novo limite: {new_limit}MB")

        except Exception as e:
            logging.error(f"Erro ao decrementar volume '{volume_name}': {e}")
            raise

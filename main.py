from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from database import Sqlite
from volume_manager import VolumeManager
from container_manager import ContainerManager
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="🐳 Docker + SQLite Manager API", version="1.0")

# Instâncias globais
db = Sqlite()
volume_manager = VolumeManager("/var/lib/docker-imgs", db)
container_manager = ContainerManager(volume_manager, db)

# ---------------------------------
# Página inicial - lista todas as rotas
# ---------------------------------
@app.get("/", tags=["Home"])
def home():
    routes_info = []
    for route in app.routes:
        if hasattr(route, "methods"):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name
            })
    return {"message": "🚀 API disponível!", "routes": routes_info}


# ---------------------------------
# Usuários
# ---------------------------------
@app.post("/usuarios/criar", tags=["Usuários"])
def criar_usuario(username: str, level: str = "user", limite_mb: int = 1024):
    try:
        db.add_user(username, level, limite_mb)
        vol = volume_manager.on_user_created(username)
        return {
            "status": "✅ Usuário criado com sucesso",
            "usuario": username,
            "volume": vol
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/usuarios/{username}", tags=["Usuários"])
def deletar_usuario(username: str):
    try:
        # remove containers do usuário
        containers = [c for c in db.list_containers() if c["usuario"] == username]
        for c in containers:
            container_manager.remove_container(c["id"])

        # remove volumes
        volume_manager.on_user_deleted(username)

        # remove do banco
        db.cursor.execute("DELETE FROM users WHERE username=?", (username,))
        db.conn.commit()

        return {"status": f"✅ Usuário '{username}' removido com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/usuarios", tags=["Usuários"])
def listar_usuarios():
    users = db.list_users()
    if not users:
        return {"message": "Nenhum usuário encontrado"}
    return users


# ---------------------------------
# Volumes
# ---------------------------------
@app.get("/volumes", tags=["Volumes"])
def listar_volumes():
    vols = db.list_volumes()
    if not vols:
        return {"message": "Nenhum volume encontrado"}
    return vols


@app.get("/volumes/espaco", tags=["Volumes"])
def consultar_espaco():
    vols = db.list_volumes()
    resultado = []
    for v in vols:
        try:
            usage = volume_manager.get_volume_usage(v["name"])
            resultado.append({
                "volume": v["name"],
                "uso": usage
            })
        except Exception as e:
            resultado.append({
                "volume": v["name"],
                "erro": str(e)
            })
    return resultado


# ---------------------------------
# Containers
# ---------------------------------
@app.post("/containers/criar", tags=["Containers"])
def criar_container(usuario: str, tipodb: str):
    try:
        info = container_manager.create_container(usuario, tipodb)
        return {
            "status": "✅ Container criado com sucesso",
            "dados": info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/containers", tags=["Containers"])
def listar_containers():
    containers = db.list_containers()
    if not containers:
        return {"message": "Nenhum container encontrado"}
    return containers


@app.post("/containers/{cid}/iniciar", tags=["Containers"])
def iniciar_container(cid: str):
    try:
        container_manager.start_container(cid)
        return {"status": f"✅ Container {cid} iniciado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/containers/{cid}/parar", tags=["Containers"])
def parar_container(cid: str):
    try:
        container_manager.stop_container(cid)
        return {"status": f"🛑 Container {cid} parado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/containers/{cid}", tags=["Containers"])
def remover_container(cid: str):
    try:
        container_manager.remove_container(cid)
        return {"status": f"🗑️ Container {cid} removido"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

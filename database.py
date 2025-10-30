import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

class Sqlite:
    def __init__(self, db_path="saas.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        logging.info(f"Banco SQLite inicializado: {db_path}")

    # -------------------------
    # Inicialização do banco
    # -------------------------
    def _init_db(self):
        # Tabela de usuários
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                storage_limit_mb INTEGER DEFAULT 1024
            )
        """)

        # Tabela de volumes
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS volumes (
                name TEXT PRIMARY KEY,
                usuario_responsavel TEXT NOT NULL,
                path TEXT NOT NULL,
                limite_mb INTEGER NOT NULL,
                FOREIGN KEY(usuario_responsavel) REFERENCES users(username)
            )
        """)

        # Tabela de containers
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS containers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_name TEXT NOT NULL,
                usuario TEXT NOT NULL,
                tipodb TEXT NOT NULL,
                loginroot TEXT NOT NULL,
                password TEXT NOT NULL,
                porta INTEGER NOT NULL,
                FOREIGN KEY(usuario) REFERENCES users(username)
            )
        """)

        self.conn.commit()

    # -------------------------
    # Usuários
    # -------------------------
    def add_user(self, username, level, storage_limit_mb=5000):
        try:
            self.cursor.execute(
                "INSERT INTO users (username, level, storage_limit_mb) VALUES (?, ?, ?)",
                (username, level, storage_limit_mb)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Usuário {username} já existe")

    def get_user_limit(self, username):
        self.cursor.execute("SELECT storage_limit_mb FROM users WHERE username=?", (username,))
        row = self.cursor.fetchone()
        return row[0] if row else 0

    def list_users(self):
        self.cursor.execute("SELECT username, level, storage_limit_mb FROM users")
        rows = self.cursor.fetchall()
        return [{"username": u, "level": l, "storage_limit_mb": s} for u, l, s in rows]

    # -------------------------
    # Volumes
    # -------------------------
    def add_volume(self, name, usuario_responsavel, path, limite_mb):
        try:
            self.cursor.execute(
                "INSERT INTO volumes (name, usuario_responsavel, path, limite_mb) VALUES (?, ?, ?, ?)",
                (name, usuario_responsavel, path, limite_mb)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Volume {name} já existe")

    def update_volume_limit(self, name, new_limit):
        self.cursor.execute(
            "UPDATE volumes SET limite_mb=? WHERE name=?",
            (new_limit, name)
        )
        self.conn.commit()

    def delete_volume(self, name):
        self.cursor.execute("DELETE FROM volumes WHERE name=?", (name,))
        self.conn.commit()

    def get_volume(self, name):
        self.cursor.execute("SELECT name, usuario_responsavel, path, limite_mb FROM volumes WHERE name=?", (name,))
        row = self.cursor.fetchone()
        if row:
            return {"name": row[0], "usuario_responsavel": row[1], "path": row[2], "limite_mb": row[3]}
        return None

    def list_volumes(self):
        self.cursor.execute("SELECT name, usuario_responsavel, path, limite_mb FROM volumes")
        rows = self.cursor.fetchall()
        return [{"name": r[0], "usuario_responsavel": r[1], "path": r[2], "limite_mb": r[3]} for r in rows]

    # -------------------------
    # Containers
    # -------------------------
    def add_container(self, container_name, usuario, tipodb, loginroot, password, porta):
        try:
            self.cursor.execute(
                """
                INSERT INTO containers (container_name, usuario, tipodb, loginroot, password, porta)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (container_name, usuario, tipodb, loginroot, password, porta)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Container '{container_name}' já existe ou duplicado para usuário {usuario}")

    def get_container(self, container_name):
        self.cursor.execute(
            "SELECT id, container_name, usuario, tipodb, loginroot, password, porta FROM containers WHERE container_name=?",
            (container_name,)
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "container_name": row[1],
                "usuario": row[2],
                "tipodb": row[3],
                "loginroot": row[4],
                "password": row[5],
                "porta": row[6]
            }
        return None

    def list_containers(self):
        self.cursor.execute("SELECT id, container_name, usuario, tipodb, loginroot, password, porta FROM containers")
        rows = self.cursor.fetchall()
        return [
            {
                "id": r[0],
                "container_name": r[1],
                "usuario": r[2],
                "tipodb": r[3],
                "loginroot": r[4],
                "password": r[5],
                "porta": r[6]
            }
            for r in rows
        ]

    def delete_container(self, container_name):
        self.cursor.execute("DELETE FROM containers WHERE container_name=?", (container_name,))
        self.conn.commit()

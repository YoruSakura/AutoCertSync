"""SQLite 数据模块 - 表结构定义与 CRUD 操作"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    auth_type TEXT NOT NULL DEFAULT 'password',
    username TEXT NOT NULL,
    password TEXT,
    private_key TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cert_dirs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_path TEXT NOT NULL UNIQUE,
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deploy_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    cert_dir_id INTEGER NOT NULL,
    remote_cert_dir TEXT NOT NULL,
    pre_deploy_command TEXT,
    post_deploy_command TEXT,
    cert_filename TEXT,
    key_filename TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    FOREIGN KEY (cert_dir_id) REFERENCES cert_dirs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER,
    cert_dir_id INTEGER,
    deploy_rule_id INTEGER,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE SET NULL,
    FOREIGN KEY (cert_dir_id) REFERENCES cert_dirs(id) ON DELETE SET NULL,
    FOREIGN KEY (deploy_rule_id) REFERENCES deploy_rules(id) ON DELETE SET NULL
);
"""

# ohttps 默认文件名 -> NGINX 默认文件名
DEFAULT_CERT_FILENAME = "fullchain.pem"
DEFAULT_KEY_FILENAME = "privkey.pem"


class Database:
    """SQLite 数据库管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA_SQL)

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ========== servers CRUD ==========

    def add_server(self, name: str, host: str, port: int, auth_type: str,
                   username: str, password: str = None, private_key: str = None,
                   enabled: int = 1) -> int:
        now = self._now()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO servers (name, host, port, auth_type, username, "
                "password, private_key, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, host, port, auth_type, username, password, private_key,
                 enabled, now, now)
            )
            return cursor.lastrowid

    def update_server(self, server_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        kwargs["updated_at"] = self._now()
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [server_id]
        with self._get_conn() as conn:
            conn.execute(f"UPDATE servers SET {fields} WHERE id = ?", values)
            return True

    def delete_server(self, server_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))

    def get_server(self, server_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
            return dict(row) if row else None

    def list_servers(self, enabled_only: bool = False) -> list[dict]:
        with self._get_conn() as conn:
            sql = "SELECT * FROM servers"
            if enabled_only:
                sql += " WHERE enabled = 1"
            sql += " ORDER BY id"
            return [dict(row) for row in conn.execute(sql).fetchall()]

    # ========== cert_dirs CRUD ==========

    def add_cert_dir(self, local_path: str, description: str = None,
                     enabled: int = 1) -> int:
        now = self._now()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO cert_dirs (local_path, description, enabled, created_at) "
                "VALUES (?, ?, ?, ?)",
                (local_path, description, enabled, now)
            )
            return cursor.lastrowid

    def update_cert_dir(self, cert_dir_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [cert_dir_id]
        with self._get_conn() as conn:
            conn.execute(f"UPDATE cert_dirs SET {fields} WHERE id = ?", values)
            return True

    def delete_cert_dir(self, cert_dir_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cert_dirs WHERE id = ?", (cert_dir_id,))

    def get_cert_dir(self, cert_dir_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM cert_dirs WHERE id = ?", (cert_dir_id,)).fetchone()
            return dict(row) if row else None

    def list_cert_dirs(self, enabled_only: bool = False) -> list[dict]:
        with self._get_conn() as conn:
            sql = "SELECT * FROM cert_dirs"
            if enabled_only:
                sql += " WHERE enabled = 1"
            sql += " ORDER BY id"
            return [dict(row) for row in conn.execute(sql).fetchall()]

    # ========== deploy_rules CRUD ==========

    def add_deploy_rule(self, server_id: int, cert_dir_id: int,
                        remote_cert_dir: str, pre_deploy_command: str = None,
                        post_deploy_command: str = None,
                        cert_filename: str = None, key_filename: str = None,
                        enabled: int = 1) -> int:
        now = self._now()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO deploy_rules (server_id, cert_dir_id, remote_cert_dir, "
                "pre_deploy_command, post_deploy_command, cert_filename, key_filename, "
                "enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (server_id, cert_dir_id, remote_cert_dir, pre_deploy_command,
                 post_deploy_command, cert_filename, key_filename, enabled, now)
            )
            return cursor.lastrowid

    def update_deploy_rule(self, rule_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [rule_id]
        with self._get_conn() as conn:
            conn.execute(f"UPDATE deploy_rules SET {fields} WHERE id = ?", values)
            return True

    def delete_deploy_rule(self, rule_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM deploy_rules WHERE id = ?", (rule_id,))

    def get_deploy_rule(self, rule_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM deploy_rules WHERE id = ?", (rule_id,)).fetchone()
            return dict(row) if row else None

    def list_deploy_rules(self, server_id: int = None, cert_dir_id: int = None,
                          enabled_only: bool = False) -> list[dict]:
        conditions = []
        params = []
        if server_id is not None:
            conditions.append("r.server_id = ?")
            params.append(server_id)
        if cert_dir_id is not None:
            conditions.append("r.cert_dir_id = ?")
            params.append(cert_dir_id)
        if enabled_only:
            conditions.append("r.enabled = 1")

        sql = (
            "SELECT r.*, s.name AS server_name, s.host AS server_host, "
            "cd.local_path AS cert_dir_path, cd.description AS cert_dir_desc "
            "FROM deploy_rules r "
            "LEFT JOIN servers s ON r.server_id = s.id "
            "LEFT JOIN cert_dirs cd ON r.cert_dir_id = cd.id"
        )
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY r.id"
        with self._get_conn() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_rules_for_cert_dir(self, cert_dir_id: int) -> list[dict]:
        """获取某证书目录的所有启用的部署规则（含服务器信息）"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT r.*, s.name AS server_name, s.host AS server_host, "
                "s.port AS server_port, s.auth_type, s.username, s.password, "
                "s.private_key "
                "FROM deploy_rules r "
                "JOIN servers s ON r.server_id = s.id "
                "WHERE r.cert_dir_id = ? AND r.enabled = 1 AND s.enabled = 1 "
                "ORDER BY r.id",
                (cert_dir_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    # ========== sync_logs ==========

    def add_sync_log(self, server_id: int, cert_dir_id: int,
                     status: str, message: str = None,
                     deploy_rule_id: int = None) -> int:
        now = self._now()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO sync_logs (server_id, cert_dir_id, deploy_rule_id, "
                "status, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (server_id, cert_dir_id, deploy_rule_id, status, message, now)
            )
            row_id = cursor.lastrowid
        self.clear_sync_logs(20)
        return row_id

    def list_sync_logs(self, limit: int = 100, server_id: int = None,
                       cert_dir_id: int = None) -> list[dict]:
        conditions = []
        params = []
        if server_id is not None:
            conditions.append("l.server_id = ?")
            params.append(server_id)
        if cert_dir_id is not None:
            conditions.append("l.cert_dir_id = ?")
            params.append(cert_dir_id)

        sql = (
            "SELECT l.*, s.name AS server_name, s.host AS server_host "
            "FROM sync_logs l "
            "LEFT JOIN servers s ON l.server_id = s.id"
        )
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY l.id DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def clear_sync_logs(self, keep_recent: int = 20):
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM sync_logs WHERE id NOT IN "
                "(SELECT id FROM sync_logs ORDER BY id DESC LIMIT ?)",
                (keep_recent,)
            )

    # ========== 导入导出 ==========

    def export_config(self) -> dict:
        servers = self.list_servers()
        cert_dirs = self.list_cert_dirs()
        rules = []
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, server_id, cert_dir_id, remote_cert_dir, "
                "pre_deploy_command, post_deploy_command, "
                "cert_filename, key_filename, enabled FROM deploy_rules"
            ).fetchall()
            rules = [dict(row) for row in rows]
        return {
            "servers": servers,
            "cert_dirs": cert_dirs,
            "deploy_rules": rules,
        }

    def import_config(self, data: dict):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM deploy_rules")
            conn.execute("DELETE FROM servers")
            conn.execute("DELETE FROM cert_dirs")

            id_map_servers = {}
            for s in data.get("servers", []):
                old_id = s.pop("id", None)
                s.pop("created_at", None)
                s.pop("updated_at", None)
                now = self._now()
                cursor = conn.execute(
                    "INSERT INTO servers (name, host, port, auth_type, username, "
                    "password, private_key, enabled, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (s["name"], s["host"], s.get("port", 22), s.get("auth_type", "password"),
                     s["username"], s.get("password"), s.get("private_key"),
                     s.get("enabled", 1), now, now)
                )
                if old_id is not None:
                    id_map_servers[old_id] = cursor.lastrowid

            id_map_dirs = {}
            for cd in data.get("cert_dirs", []):
                old_id = cd.pop("id", None)
                cd.pop("created_at", None)
                now = self._now()
                cursor = conn.execute(
                    "INSERT INTO cert_dirs (local_path, description, enabled, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (cd["local_path"], cd.get("description"), cd.get("enabled", 1), now)
                )
                if old_id is not None:
                    id_map_dirs[old_id] = cursor.lastrowid

            for rule in data.get("deploy_rules", []):
                rule.pop("id", None)
                rule.pop("created_at", None)
                new_srv_id = id_map_servers.get(rule.get("server_id"))
                new_dir_id = id_map_dirs.get(rule.get("cert_dir_id"))
                if new_srv_id and new_dir_id:
                    now = self._now()
                    conn.execute(
                        "INSERT INTO deploy_rules (server_id, cert_dir_id, remote_cert_dir, "
                        "pre_deploy_command, post_deploy_command, cert_filename, "
                        "key_filename, enabled, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (new_srv_id, new_dir_id, rule["remote_cert_dir"],
                         rule.get("pre_deploy_command"), rule.get("post_deploy_command"),
                         rule.get("cert_filename"),
                         rule.get("key_filename"), rule.get("enabled", 1), now)
                    )

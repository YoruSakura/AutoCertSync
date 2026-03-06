"""证书同步引擎 - 编排完整的远端部署流程"""

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from autocertsync.ssh_client import SSHClient
from autocertsync.cert_utils import (
    local_cert_valid, file_sha256, find_cert_files,
    remote_cert_hash_command, remote_cert_verify_command,
)
from autocertsync.database import Database, DEFAULT_CERT_FILENAME, DEFAULT_KEY_FILENAME
from autocertsync.logger import get_logger

REMOTE_TMP_DIR = "/tmp/autocertsync"

# ohttps 源文件名映射
OHTTPS_FILE_MAP = {
    "fullchain.cer": "cert",
    "cert.key": "key",
}


class SyncEngine:
    """证书同步引擎"""

    def __init__(self, db: Database, retry_count: int = 3, retry_interval: int = 10):
        self.db = db
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._shutting_down = threading.Event()
        self._active_tasks = 0
        self._tasks_lock = threading.Lock()

    def shutdown(self):
        logger = get_logger()
        self._shutting_down.set()
        logger.info("同步引擎正在关闭，等待当前任务完成...")
        self._executor.shutdown(wait=True)
        logger.info("同步引擎已关闭")

    @property
    def is_busy(self) -> bool:
        with self._tasks_lock:
            return self._active_tasks > 0

    def sync_cert_dir(self, cert_dir_id: int):
        """触发某个证书目录的同步（异步执行）"""
        if self._shutting_down.is_set():
            return
        self._executor.submit(self._do_sync_cert_dir, cert_dir_id)

    def sync_rule(self, rule_id: int):
        """触发单条部署规则的同步（异步执行）"""
        if self._shutting_down.is_set():
            return
        self._executor.submit(self._do_sync_rule, rule_id)

    def sync_all(self):
        """同步所有启用的证书目录"""
        if self._shutting_down.is_set():
            return
        cert_dirs = self.db.list_cert_dirs(enabled_only=True)
        for cd in cert_dirs:
            self.sync_cert_dir(cd["id"])

    def _do_sync_cert_dir(self, cert_dir_id: int):
        """执行证书目录的完整同步流程"""
        logger = get_logger()
        with self._tasks_lock:
            self._active_tasks += 1
        try:
            cert_dir = self.db.get_cert_dir(cert_dir_id)
            if not cert_dir:
                logger.error(f"证书目录不存在: id={cert_dir_id}")
                return

            local_path = cert_dir["local_path"]
            cert_files = find_cert_files(local_path)
            if not cert_files:
                logger.info(f"证书目录无证书文件: {local_path}")
                return

            # 本地校验
            for cf in cert_files:
                if cf.endswith((".crt", ".pem", ".cer", ".cert")) and not local_cert_valid(cf):
                    logger.error(f"本地证书校验失败，中止同步: {cf}")
                    self.db.add_sync_log(0, cert_dir_id, "failed", f"本地证书校验失败: {cf}")
                    return

            # 获取此证书目录的所有部署规则
            rules = self.db.get_rules_for_cert_dir(cert_dir_id)
            if not rules:
                logger.info(f"证书目录无部署规则: {local_path}")
                return

            logger.info(f"开始同步证书目录 {local_path} -> {len(rules)} 条部署规则")
            for rule in rules:
                if self._shutting_down.is_set():
                    logger.info("收到关闭信号，停止后续同步")
                    break
                self._sync_by_rule(cert_dir_id, rule, cert_files)
        finally:
            with self._tasks_lock:
                self._active_tasks -= 1

    def _do_sync_rule(self, rule_id: int):
        """执行单条部署规则的同步"""
        logger = get_logger()
        with self._tasks_lock:
            self._active_tasks += 1
        try:
            rule = self.db.get_deploy_rule(rule_id)
            if not rule:
                logger.error(f"部署规则不存在: id={rule_id}")
                return

            cert_dir = self.db.get_cert_dir(rule["cert_dir_id"])
            server = self.db.get_server(rule["server_id"])
            if not cert_dir or not server:
                logger.error(f"部署规则关联的证书目录或服务器不存在: rule={rule_id}")
                return

            cert_files = find_cert_files(cert_dir["local_path"])
            if not cert_files:
                logger.info(f"证书目录无证书文件: {cert_dir['local_path']}")
                return

            for cf in cert_files:
                if cf.endswith((".crt", ".pem", ".cer", ".cert")) and not local_cert_valid(cf):
                    logger.error(f"本地证书校验失败，中止同步: {cf}")
                    return

            # 补充服务器连接信息到 rule
            rule_with_server = {
                **rule,
                "server_host": server["host"],
                "server_port": server["port"],
                "server_name": server["name"],
                "auth_type": server["auth_type"],
                "username": server["username"],
                "password": server.get("password"),
                "private_key": server.get("private_key"),
            }
            self._sync_by_rule(rule["cert_dir_id"], rule_with_server, cert_files)
        finally:
            with self._tasks_lock:
                self._active_tasks -= 1

    def _sync_by_rule(self, cert_dir_id: int, rule: dict, cert_files: list[str]):
        """按部署规则同步（含重试）"""
        logger = get_logger()
        server_label = f"{rule.get('server_name', '')}({rule.get('server_host', '')})"
        rule_label = f"{server_label}:{rule['remote_cert_dir']}"

        for attempt in range(1, self.retry_count + 1):
            if self._shutting_down.is_set():
                return
            try:
                self._do_sync_by_rule(cert_dir_id, rule, cert_files)
                return
            except Exception as e:
                logger.error(f"同步 {rule_label} 失败 (尝试 {attempt}/{self.retry_count}): {e}")
                if attempt < self.retry_count:
                    logger.info(f"等待 {self.retry_interval} 秒后重试...")
                    for _ in range(self.retry_interval):
                        if self._shutting_down.is_set():
                            return
                        time.sleep(1)
                else:
                    self.db.add_sync_log(
                        rule["server_id"], cert_dir_id, "failed",
                        f"重试 {self.retry_count} 次后仍然失败: {e}",
                        deploy_rule_id=rule.get("id"),
                    )

    def _get_target_filename(self, src_filename: str, rule: dict) -> str:
        """根据部署规则决定目标文件名"""
        src_lower = src_filename.lower()
        file_type = OHTTPS_FILE_MAP.get(src_lower)

        if file_type == "cert":
            custom = rule.get("cert_filename")
            return custom if custom else DEFAULT_CERT_FILENAME
        elif file_type == "key":
            custom = rule.get("key_filename")
            return custom if custom else DEFAULT_KEY_FILENAME
        else:
            # 非 ohttps 标准文件，保留原名
            return src_filename

    @staticmethod
    def _exec_commands(ssh, commands_text: str, server_label: str,
                       phase_label: str) -> tuple:
        """按行执行多条命令，任一失败则中止。
        返回 (error_msg, output_lines)：error_msg 非空表示失败，output_lines 收集所有命令输出。"""
        logger = get_logger()
        if not commands_text:
            return None, []
        lines = [ln.strip() for ln in commands_text.splitlines() if ln.strip()]
        if not lines:
            return None, []
        output_lines = []
        for cmd in lines:
            logger.info(f"[{server_label}] {phase_label}: {cmd}")
            exit_code, out, err = ssh.exec_command(cmd)
            out_stripped = out.strip() if out else ""
            err_stripped = err.strip() if err else ""
            if out_stripped:
                logger.info(f"[{server_label}] {phase_label} 输出: {out_stripped}")
                output_lines.append(f"$ {cmd}\n{out_stripped}")
            if exit_code != 0:
                logger.error(f"[{server_label}] {phase_label}失败: {err_stripped}")
                output_lines.append(f"$ {cmd} [失败]\n{err_stripped}")
                error_msg = f"{phase_label}失败({cmd}): {err_stripped}"
                return error_msg, output_lines
        return None, output_lines

    def _do_sync_by_rule(self, cert_dir_id: int, rule: dict, cert_files: list[str]):
        """实际按规则同步到服务器的流程"""
        logger = get_logger()
        server_label = f"{rule.get('server_name', '')}({rule.get('server_host', '')})"
        remote_cert_dir = rule["remote_cert_dir"]

        ssh = SSHClient(
            host=rule["server_host"],
            port=rule["server_port"],
            username=rule["username"],
            auth_type=rule["auth_type"],
            password=rule.get("password"),
            private_key=rule.get("private_key"),
        )

        with ssh:
            # 1. 创建远端临时目录
            ssh.ensure_remote_dir(REMOTE_TMP_DIR)

            # 2. 确保远端目标目录存在
            ssh.ensure_remote_dir(remote_cert_dir)

            # 3. 上传所有证书文件到临时目录
            for local_file in cert_files:
                filename = os.path.basename(local_file)
                remote_tmp_file = f"{REMOTE_TMP_DIR}/{filename}"
                ssh.upload_file(local_file, remote_tmp_file)

            # 4. 逐文件对比哈希并决定是否替换（含重命名）
            any_updated = False
            for local_file in cert_files:
                src_filename = os.path.basename(local_file)
                target_filename = self._get_target_filename(src_filename, rule)
                remote_tmp_file = f"{REMOTE_TMP_DIR}/{src_filename}"
                remote_target_file = f"{remote_cert_dir}/{target_filename}"
                local_hash = file_sha256(local_file)

                # 获取远端目标文件哈希
                exit_code, remote_hash, _ = ssh.exec_command(
                    remote_cert_hash_command(remote_target_file)
                )
                remote_hash = remote_hash.strip()

                if remote_hash == local_hash:
                    logger.info(f"[{server_label}] {target_filename} 哈希一致，跳过")
                    continue

                # 哈希不一致，验证新证书有效期（仅证书文件，非 key）
                if src_filename.lower() in ("fullchain.cer",) or \
                   src_filename.endswith((".crt", ".pem", ".cer", ".cert")):
                    exit_code, _, _ = ssh.exec_command(
                        remote_cert_verify_command(remote_tmp_file)
                    )
                    if exit_code != 0:
                        logger.warning(f"[{server_label}] {target_filename} 证书已过期或无效，跳过")
                        continue

                # 替换证书（重命名）
                exit_code, _, err = ssh.exec_command(
                    f"cp -f {remote_tmp_file} {remote_target_file}"
                )
                if exit_code != 0:
                    raise RuntimeError(f"替换文件失败 {target_filename}: {err}")
                logger.info(f"[{server_label}] {src_filename} -> {target_filename} 已更新")
                any_updated = True

            # 5. 执行部署命令
            if any_updated:
                all_output = []
                # 5a. 部署前命令
                pre_cmd = rule.get("pre_deploy_command")
                err_msg, pre_output = self._exec_commands(ssh, pre_cmd, server_label, "部署前命令")
                all_output.extend(pre_output)
                if err_msg:
                    self.db.add_sync_log(
                        rule["server_id"], cert_dir_id, "failed",
                        f"证书已更新但{err_msg}",
                        deploy_rule_id=rule.get("id"),
                    )
                else:
                    # 5b. 部署后命令
                    post_cmd = rule.get("post_deploy_command")
                    err_msg, post_output = self._exec_commands(ssh, post_cmd, server_label, "部署后命令")
                    all_output.extend(post_output)
                    if err_msg:
                        self.db.add_sync_log(
                            rule["server_id"], cert_dir_id, "failed",
                            f"证书已更新但{err_msg}",
                            deploy_rule_id=rule.get("id"),
                        )
                    else:
                        detail = "\n".join(all_output)
                        msg = f"同步并部署成功\n{detail}" if detail else "同步并部署成功"
                        self.db.add_sync_log(
                            rule["server_id"], cert_dir_id, "success",
                            msg,
                            deploy_rule_id=rule.get("id"),
                        )
            else:
                logger.info(f"[{server_label}] 所有证书无变化")
                self.db.add_sync_log(
                    rule["server_id"], cert_dir_id, "skipped",
                    "证书无变化",
                    deploy_rule_id=rule.get("id"),
                )

            # 6. 清理临时目录
            ssh.exec_command(f"rm -rf {REMOTE_TMP_DIR}")

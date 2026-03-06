"""SSH 连接模块 - paramiko 封装，支持密钥/密码认证，SFTP 优先 SCP 降级"""

import io
import os
from typing import Optional

import paramiko
from scp import SCPClient

from autocertsync.logger import get_logger


class SSHClient:
    """SSH 连接管理器"""

    def __init__(self, host: str, port: int, username: str,
                 auth_type: str = "password", password: str = None,
                 private_key: str = None, timeout: int = 30):
        self.host = host
        self.port = port
        self.username = username
        self.auth_type = auth_type
        self.password = password
        self.private_key = private_key
        self.timeout = timeout
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self):
        """建立 SSH 连接"""
        logger = get_logger()
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "timeout": self.timeout,
        }

        if self.auth_type == "key" and self.private_key:
            key_file = io.StringIO(self.private_key)
            try:
                pkey = paramiko.RSAKey.from_private_key(key_file)
            except paramiko.SSHException:
                key_file.seek(0)
                try:
                    pkey = paramiko.Ed25519Key.from_private_key(key_file)
                except paramiko.SSHException:
                    key_file.seek(0)
                    pkey = paramiko.ECDSAKey.from_private_key(key_file)
            kwargs["pkey"] = pkey
        else:
            kwargs["password"] = self.password

        self._client.connect(**kwargs)
        logger.debug(f"SSH 已连接: {self.username}@{self.host}:{self.port}")

    def disconnect(self):
        """关闭 SSH 连接"""
        if self._client:
            self._client.close()
            self._client = None

    def exec_command(self, command: str) -> tuple[int, str, str]:
        """执行远程命令，返回 (exit_code, stdout, stderr)"""
        if not self._client:
            raise RuntimeError("SSH 未连接")
        stdin, stdout, stderr = self._client.exec_command(command, timeout=self.timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        return exit_code, out, err

    def upload_file_sftp(self, local_path: str, remote_path: str):
        """通过 SFTP 上传文件"""
        if not self._client:
            raise RuntimeError("SSH 未连接")
        sftp = self._client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()

    def upload_file_scp(self, local_path: str, remote_path: str):
        """通过 SCP 上传文件"""
        if not self._client:
            raise RuntimeError("SSH 未连接")
        transport = self._client.get_transport()
        with SCPClient(transport) as scp:
            scp.put(local_path, remote_path)

    def upload_file(self, local_path: str, remote_path: str):
        """上传文件：SFTP 优先，失败后降级 SCP"""
        logger = get_logger()
        try:
            self.upload_file_sftp(local_path, remote_path)
            logger.debug(f"SFTP 上传成功: {local_path} -> {self.host}:{remote_path}")
        except Exception as e:
            logger.warning(f"SFTP 上传失败 ({e})，降级使用 SCP")
            self.upload_file_scp(local_path, remote_path)
            logger.debug(f"SCP 上传成功: {local_path} -> {self.host}:{remote_path}")

    def ensure_remote_dir(self, remote_dir: str):
        """确保远端目录存在，不存在则创建"""
        exit_code, _, err = self.exec_command(f"mkdir -p {remote_dir}")
        if exit_code != 0:
            raise RuntimeError(f"创建远端目录失败 {remote_dir}: {err}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

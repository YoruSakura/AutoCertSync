# 🔐 AutoCertSync — 自动 SSL/TLS 证书同步工具

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 📖 项目简介

AutoCertSync 是一款自动化 SSL/TLS 证书同步部署工具。

当 [ohttps](https://ohttps.com) 平台将证书推送到中心服务器后，AutoCertSync 会**自动检测证书文件变动**，并将新证书**同步部署到各子服务器**，执行指定的部署命令（如 `systemctl reload nginx`），实现证书的全自动分发与更新。

### ✨ 核心特性

- 🔍 **实时监听** — 基于 inotify 监听本地证书目录变动，防抖机制防止文件未写完即触发
- 🚀 **自动同步** — 检测到证书更新后自动上传至目标服务器并执行部署命令
- 🔑 **多种认证** — 支持 SSH 密钥认证和密码认证（基于 paramiko）
- 📂 **文件传输** — SFTP 优先，失败自动降级 SCP 重试
- 🔒 **安全校验** — 本地验证证书格式，远端 openssl 校验哈希与有效期，哈希一致则跳过
- 🖥️ **WebUI 管理** — FastAPI + Jinja2 全功能管理面板，浏览器即可操作
- 📦 **一键打包** — 打包为单个 `.pyz` 文件，部署简洁
- 🔄 **灵活规则** — 一台服务器可配置多条部署规则，支持自定义文件名映射和部署前/后命令
- 📤 **配置迁移** — 支持 YAML 格式导入导出配置，便于跨服务器迁移

---

## 🏗️ 工作流程

```
ohttps 推送证书 → 中心服务器本地目录 → AutoCertSync 检测变动
    → 上传至子服务器 /tmp/autocertsync/
    → openssl 校验哈希 & 有效期
    → 替换目标路径证书文件
    → 执行部署前/后命令
    → 清理临时目录
```

---

## 🚀 部署指南

### 📋 环境要求

- 目标 Linux 服务器需 **Python 3.8+**
- 子服务器无需安装额外软件，通过 SSH 连接即可

### 📁 部署路径结构

```
/opt/autocertsync/
├── autocertsync.pyz          # 📦 程序本体
├── venv/                     # 🐍 Python 虚拟环境
├── config.ini                # ⚙️ 程序配置（首次运行自动生成）
├── data/
│   ├── autocertsync.db       # 🗄️ SQLite 数据库
│   ├── autocertsync.log      # 📝 日志文件
│   └── web/                  # 🌐 Web 资源（自动提取）
└── ssl/                      # 🔐 HTTPS 证书目录（可选）
```

### 📥 安装步骤

**1️⃣ 打包程序**（在开发机上执行）

```bash
python build.py
```

生成 `autocertsync.pyz` 文件。

**2️⃣ 上传到服务器**

将 `autocertsync.pyz` 和 `requirements.txt` 上传到目标服务器的 `/opt/autocertsync/` 目录。

**3️⃣ 创建虚拟环境并安装依赖**

```bash
python3 -m venv /opt/autocertsync/venv
/opt/autocertsync/venv/bin/pip install -r /opt/autocertsync/requirements.txt
```

**4️⃣ 首次运行**

```bash
/opt/autocertsync/venv/bin/python /opt/autocertsync/autocertsync.pyz
```

首次运行会自动生成 `config.ini` 配置文件和 SQLite 数据库。

**5️⃣ 注册为 systemd 服务（推荐）**

```bash
sudo /opt/autocertsync/venv/bin/python /opt/autocertsync/autocertsync.pyz install
```

卸载服务：

```bash
sudo /opt/autocertsync/venv/bin/python /opt/autocertsync/autocertsync.pyz uninstall
```

---

## ⚙️ 初始化配置

### 1️⃣ 程序配置 — config.ini

首次运行自动生成，可手动编辑，包含以下配置项：

| 配置段 | 说明 |
|--------|------|
| `[webui]` | WebUI 端口等设置 |
| `[database]` | 数据库路径 |
| `[log]` | 日志级别、轮转大小 (`max_size_mb`)、备份数 (`backup_count`) |
| `[ssl]` | HTTPS 证书配置 |

### 2️⃣ 业务配置 — WebUI 管理

启动程序后，打开浏览器访问 WebUI（默认管理员账号在 config.ini 中配置），通过面板完成以下配置：

- **🖥️ 添加服务器** — 配置子服务器的 SSH 连接信息（主机、端口、认证方式）
- **📂 添加证书目录** — 配置本地监听的证书文件夹路径
- **📋 创建部署规则** — 关联服务器与证书目录，设置远程部署路径和部署命令

### 3️⃣ 启用 HTTPS（可选）

在 `/opt/autocertsync/ssl/` 目录放入：
- `server.crt` — 证书文件
- `server.key` — 私钥文件

程序会自动检测并启用 HTTPS，目录为空则以 HTTP 方式运行。

---

## 🖥️ WebUI 功能一览

| 功能 | 说明 |
|------|------|
| 📊 仪表盘 | 同步状态总览、各服务器连接状态 |
| 🖥️ 服务器管理 | 增删改服务器连接信息 |
| 📂 证书目录 | 管理监听的本地证书目录，查看证书详情（域名、有效期、颁发者） |
| 📋 部署规则 | 配置部署路径、文件名映射、部署前/后命令 |
| 🔄 手动同步 | 一键全量同步或针对单台服务器同步 |
| 📝 日志查看 | 查看最近日志内容，支持手动刷新 |
| 📤 配置导入导出 | YAML 格式导入导出，便于迁移 |

---

## 📄 文件名映射

ohttps 推送的证书文件名会自动重命名：

| 源文件名 | 默认目标文件名 |
|----------|----------------|
| `fullchain.cer` | `fullchain.pem` |
| `cert.key` | `privkey.pem` |

每条部署规则可自定义目标文件名，留空则使用默认值。

---

## ⚠️ 升级注意事项

数据库 schema 在迭代中有较大变更，升级时需**删除旧的 `.db` 文件**让程序重新生成，然后重新通过 WebUI 配置业务数据（或使用 YAML 导入功能恢复）。

---

## 🛠️ 技术栈

- **Python 3.8+** — 运行环境
- **FastAPI + Jinja2** — Web 框架与模板引擎
- **paramiko** — SSH 连接与文件传输
- **watchdog** — 文件系统事件监听（inotify）
- **SQLite** — 轻量级数据存储
- **zipapp (.pyz)** — 单文件打包分发

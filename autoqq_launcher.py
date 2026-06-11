#!/usr/bin/env python3
"""
AutoQQ 启动器 - 统一图形化管理界面
一键启动 Bot 服务 + 筛选工具
"""

import os
import sys
import time
import json
import ctypes
import socket
import signal
import threading
import subprocess
import urllib.request
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox
from queue import Queue, Empty


# ─── 工具函数 ────────────────────────────────────────────────

# PyInstaller 打包后 sys.frozen=True，exe 所在目录即 BASE_DIR
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).parent.resolve()

PMHQ_DIR = BASE_DIR / "rbt" / "bin" / "pmhq"
LLBOT_DIR = BASE_DIR / "rbt" / "bin" / "llbot"
API_URL = "http://127.0.0.1:8099/"


def find_node_exe():
    """查找 node.exe 的完整路径，支持多种安装方式"""
    # 方法 1: 系统 PATH 中的 node
    result = subprocess.run(
        ["where", "node"], capture_output=True, text=True, timeout=3,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    if result.stdout.strip():
        return result.stdout.strip().split("\n")[0]

    # 方法 2: 常见安装位置
    common_paths = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        r"C:\Users\*\AppData\Local\Programs\nodejs\node.exe",
        os.path.expanduser(r"~\.fnm\fnm.exe"),
        r"C:\Users\*\AppData\Local\fnm\fnm.exe",
    ]
    for pattern in common_paths:
        if "*" in pattern:
            base = pattern.split("*")[0].rstrip("\\")
            for p in Path(base).parent.glob(pattern.split("*")[1] + "*"):
                exe = p / "node.exe"
                if exe.exists():
                    return str(exe)
        else:
            p = Path(pattern)
            if p.exists():
                return str(p)
    return "node"  # fallback，还是找不到就返回 node


def check_nodejs():
    """检测 Node.js 是否安装"""
    node_exe = find_node_exe()
    if node_exe == "node":
        try:
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, "未安装"
        except Exception:
            return False, "未安装"
    else:
        try:
            result = subprocess.run(
                [node_exe, "--version"], capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True, f"已安装 ({result.stdout.strip()})"
            return False, "安装损坏"
        except Exception:
            return False, "无法验证"


def _tasklist_check(exe_name):
    """通过 tasklist 检测进程是否存在（兼容中文 Windows GBK 编码）"""
    try:
        result = subprocess.run(
            ["tasklist", "/fi", f"imagename eq {exe_name}", "/fo", "csv", "/nh"],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # Windows 中文版 tasklist 输出为 GBK 编码
        output = result.stdout.decode("gbk", errors="replace")
        return exe_name in output
    except Exception:
        return False


def check_qq_running():
    """检测 QQ 是否在运行"""
    return _tasklist_check("QQ.exe")


def check_pmhq_running():
    """检测 PMHQ 是否在运行"""
    return _tasklist_check("pmhq-win-x64.exe")


def check_node_running():
    """检测 Node.js bot 进程是否在运行"""
    return _tasklist_check("node.exe")


def check_api_ready():
    """检测 API 是否可用"""
    try:
        req = urllib.request.Request(
            API_URL + "get_login_info",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data.get("data", {}).get("nickname", "未知")
    except Exception:
        return False, ""


def port_in_use(port):
    """检测端口是否被占用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result == 0
    except Exception:
        return False


# ─── 服务器启动线程 ──────────────────────────────────────────

class ServerStarter(threading.Thread):
    """后台启动 Bot 服务的线程"""

    def __init__(self, log_queue, config):
        super().__init__(daemon=True)
        self.log_queue = log_queue
        self.config = config
        self._stop_flag = False
        self.pmhq_proc = None
        self.node_proc = None

    def stop(self):
        self._stop_flag = True
        self._kill_processes()

    def _kill_processes(self, kill_qq=False):
        """清理所有相关进程"""
        killed_any = False
        try:
            # 先杀 bot 和桥接
            for proc_name, label in [
                ("pmhq-win-x64.exe", "PMHQ"),
                ("node.exe", "Node.js"),
            ]:
                r = subprocess.run(
                    ["taskkill", "/f", "/im", proc_name],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if r.returncode == 0:
                    killed_any = True
                    self.log_queue.put(("log", f"  已终止 {label} 进程"))

            # 如果需要冷启动注入，也杀掉 QQ
            if kill_qq:
                r = subprocess.run(
                    ["taskkill", "/f", "/im", "QQ.exe"],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if r.returncode == 0:
                    killed_any = True
                    self.log_queue.put(("log", "  已终止 QQ 进程（冷启动注入需要）"))

            # 等待进程真正退出
            if killed_any:
                time.sleep(3)

            # 二次确认端口释放
            for port in [13000, 8099]:
                if port_in_use(port):
                    self.log_queue.put(("log", f"  端口 {port} 仍被占用，强制释放..."))
                    subprocess.run(
                        f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port}\') do taskkill /f /pid %a >nul 2>&1',
                        shell=True, capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    time.sleep(1)
        except Exception:
            pass

    def run(self):
        try:
            # ── 第一步：清理旧进程 ──
            self.log_queue.put(("log", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
            self.log_queue.put(("log", "[1/3] 正在清理旧进程..."))
            self._kill_processes(kill_qq=True)
            time.sleep(2)

            if self._stop_flag:
                return

            # ── 第二步：启动 PMHQ（冷注入：先杀QQ再让PMHQ重新启动QQ）──
            self.log_queue.put(("log", "[2/3] 正在启动 QQ 通信桥接 (PMHQ 冷注入)..."))
            self.log_queue.put(("log", "  注意：PMHQ 将重启 QQ 客户端，请等待 QQ 重新登录"))
            self.log_queue.put(("status_pmhq", "启动中"))

            if not PMHQ_DIR.exists():
                self.log_queue.put(("error", f"错误：找不到 PMHQ 目录 {PMHQ_DIR}"))
                return

            pmhq_exe = PMHQ_DIR / "pmhq-win-x64.exe"
            if not pmhq_exe.exists():
                self.log_queue.put(("error", f"错误：找不到 PMHQ 可执行文件\n{pmhq_exe}\n\n"
                                              "请从 https://github.com/linyuchen/PMHQ/releases 下载"))
                return

            # PMHQ 冷注入：先杀 QQ → PMHQ 自行启动 QQ（作为子进程）→ 无需管理员
            # 与 run_rbt.bat 行为完全一致
            self.log_queue.put(("log", "  正在启动 PMHQ（将自动重启 QQ 客户端）..."))
            self.pmhq_proc = subprocess.Popen(
                [str(pmhq_exe)],
                cwd=str(PMHQ_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(3)

            # 等待 PMHQ 启动 QQ 并打开端口 13000（冷注入：启动 QQ → 登录 → DLL 加载）
            self.log_queue.put(("log", "  等待 PMHQ 冷启动注入 (QQ 正在重新启动)..."))
            injected = False
            for i in range(40):  # 最长等 40 秒
                time.sleep(1)
                if port_in_use(13000):
                    injected = True
                    elapsed = i + 1
                    self.log_queue.put(("log", f"  QQ 桥接已建立 (耗时 {elapsed}秒)"))
                    break
                if self._stop_flag:
                    return
                # 每 10 秒报告一次等待状态
                if (i + 1) % 10 == 0:
                    self.log_queue.put(("log", f"  等待中... ({i+1}秒, QQ 可能正在登录)"))

            if not injected:
                self.log_queue.put(("error",
                    'PMHQ 冷注入超时！端口 13000 未打开。\n\n'
                    '可能原因：\n'
                    '1) QQ 未自动登录（请手动打开 QQ 登录后重试）\n'
                    '2) 杀毒软件拦截了 PMHQ\n'
                    '3) QQ 版本与 PMHQ 不兼容'))
                return

            self.log_queue.put(("log", "  PMHQ 注入成功，桥接已建立"))
            self.log_queue.put(("status_pmhq", "运行中"))

            if self._stop_flag:
                return

            # ── 第三步：启动 Bot ──
            self.log_queue.put(("log", "[3/3] 正在启动 Bot 服务..."))
            self.log_queue.put(("status_node", "启动中"))

            if not LLBOT_DIR.exists():
                self.log_queue.put(("error", f"错误：找不到 Bot 目录 {LLBOT_DIR}"))
                return

            # 获取 node 完整路径
            node_exe = find_node_exe()

            # 启动时捕获 stdout 和 stderr，以便显示错误信息
            try:
                self.node_proc = subprocess.Popen(
                    [node_exe, "--enable-source-maps", "llbot.js", "--", "--pmhq-port=13000"],
                    cwd=str(LLBOT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except FileNotFoundError:
                self.log_queue.put(("error", "找不到 node.exe！\n"
                                              "Node.js 未安装或环境变量未生效。\n\n"
                                              "请尝试：\n"
                                              "1) 安装 Node.js: https://nodejs.org/\n"
                                              "2) 安装后重启电脑或至少重启本启动器\n"
                                              "3) 如果已安装但仍找不到，请在终端运行 'where node' 查看路径"))
                return

            time.sleep(5)

            if self.node_proc.poll() is not None:
                # 进程异常退出，获取错误输出
                output = self.node_proc.stdout.read()
                error_msg = output.strip() if output else "进程异常退出 (无错误信息)"
                # 截取关键错误信息
                lines = error_msg.split("\n")
                display = "\n".join(lines[-10:]) if len(lines) > 10 else error_msg
                self.log_queue.put(("error", f"Bot 启动失败！\n{display}"))
                return

            self.log_queue.put(("log", "  Bot 服务启动成功"))
            self.log_queue.put(("status_node", "运行中"))

            # ── 第四步：等待 API 就绪 ──
            self.log_queue.put(("log", "正在等待 API 就绪..."))
            self.log_queue.put(("status_api", "等待中"))

            max_wait = 30
            nickname = ""
            for i in range(max_wait):
                if self._stop_flag:
                    return
                ready, nick = check_api_ready()
                if ready:
                    nickname = nick
                    break
                time.sleep(1)
            else:
                # 超时
                if self.node_proc and self.node_proc.poll() is None:
                    self.log_queue.put(("log", "API 响应超时，但 Bot 进程正在运行"))
                    self.log_queue.put(("status_api", "超时"))
                    self.log_queue.put(("all_ready", True))
                    self.log_queue.put(("log", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
                    self.log_queue.put(("log", "  提示：首次使用需在浏览器设置 WebUI 密码"))
                    self.log_queue.put(("log", "  地址: http://127.0.0.1:3080"))
                    self.log_queue.put(("log", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
                else:
                    self.log_queue.put(("error", "Bot 服务未能正常启动，请查看上方日志排查"))
                return

            # ── 第五步：验证桥接是否真正可用 ──
            self.log_queue.put(("log", f"API 已就绪 (账号: {nickname})，正在验证桥接..."))
            self.log_queue.put(("status_api", "验证中"))
            self.log_queue.put(("tip", "正在验证 QQ 桥接连接，请稍候..."))

            bridge_ok = False
            for attempt in range(3):
                if self._stop_flag:
                    return
                try:
                    req = urllib.request.Request(
                        API_URL + "get_stranger_info",
                        data=json.dumps({"user_id": nickname}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                        if result.get("status") == "ok" or "data" in result:
                            bridge_ok = True
                            self.log_queue.put(("log", "  ✓ 桥接验证通过，连接稳定"))
                            break
                except Exception:
                    if attempt < 2:
                        self.log_queue.put(("log", f"  验证中... (第{attempt+1}次) "))
                        time.sleep(2)

            if bridge_ok:
                self.log_queue.put(("status_api", "就绪"))
            else:
                self.log_queue.put(("log", "  ⚠ 桥接响应较慢，但 API 端口正常，可以尝试使用"))
                self.log_queue.put(("status_api", "就绪(慢)"))

            self.log_queue.put(("all_ready", True))
            self.log_queue.put(("log", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
            self.log_queue.put(("log", "  所有服务启动完成，可以使用筛选工具了！"))
            self.log_queue.put(("log", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))

        except Exception as e:
            self.log_queue.put(("error", f"启动过程出错: {e}"))


# ─── GUI ─────────────────────────────────────────────────────

class AutoQQLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoQQ 启动器")
        self.root.geometry("700x600")
        self.root.minsize(600, 500)
        self.root.configure(bg="#f5f5f5")

        # 状态变量
        self.queue = Queue()
        self.server_thread = None
        self.all_ready = False

        # 图标颜色定义
        self.COLORS = {
            "green": "#4CAF50",
            "red": "#F44336",
            "orange": "#FF9800",
            "blue": "#2196F3",
            "gray": "#9E9E9E",
            "bg": "#f5f5f5",
            "card": "#ffffff",
        }

        self._build_ui()
        self._poll_queue()
        self._auto_check_env()
        self._periodic_check_qq()  # 每5秒重新检测QQ状态

    # ── UI 构建 ──────────────────────────────────────────

    def _build_ui(self):
        # 标题栏
        header = tk.Frame(self.root, bg=self.COLORS["blue"], height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="AutoQQ 启动器",
                 bg=self.COLORS["blue"], fg="white",
                 font=("微软雅黑", 16, "bold"), pady=10).pack()

        main = tk.Frame(self.root, bg=self.COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── 环境检测卡片 ──
        env_card = tk.LabelFrame(main, text=" 环境检测 ", font=("微软雅黑", 11, "bold"),
                                  bg=self.COLORS["card"], fg="#333", padx=12, pady=8)
        env_card.pack(fill=tk.X, pady=(0, 8))

        # Node.js 检测
        row1 = tk.Frame(env_card, bg=self.COLORS["card"])
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Node.js 运行环境:", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.nodejs_status = tk.Label(row1, text="检测中...", bg=self.COLORS["card"],
                                       font=("微软雅黑", 10), fg=self.COLORS["orange"])
        self.nodejs_status.pack(side=tk.LEFT, padx=(5, 10))
        self.nodejs_install_btn = tk.Button(row1, text="下载安装 Node.js",
                                             command=self._open_nodejs_download,
                                             bg="#FF9800", fg="white",
                                             font=("微软雅黑", 8), relief=tk.FLAT,
                                             cursor="hand2")

        # QQ 检测
        row2 = tk.Frame(env_card, bg=self.COLORS["card"])
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="QQ 客户端:", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.qq_status = tk.Label(row2, text="检测中...", bg=self.COLORS["card"],
                                   font=("微软雅黑", 10), fg=self.COLORS["orange"])
        self.qq_status.pack(side=tk.LEFT, padx=(5, 10))

        # Bot 框架检测
        row3 = tk.Frame(env_card, bg=self.COLORS["card"])
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Bot 框架文件:", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.botfile_status = tk.Label(row3, text="检测中...", bg=self.COLORS["card"],
                                        font=("微软雅黑", 10), fg=self.COLORS["orange"])
        self.botfile_status.pack(side=tk.LEFT, padx=(5, 10))

        # PMHQ 文件检测
        row4 = tk.Frame(env_card, bg=self.COLORS["card"])
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="PMHQ 桥接文件:", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.pmhqfile_status = tk.Label(row4, text="检测中...", bg=self.COLORS["card"],
                                        font=("微软雅黑", 10), fg=self.COLORS["orange"])
        self.pmhqfile_status.pack(side=tk.LEFT, padx=(5, 10))

        # 换电脑提示
        hint_frame = tk.Frame(env_card, bg="#E3F2FD")
        hint_frame.pack(fill=tk.X, pady=(6, 0))
        tk.Label(hint_frame, text="换电脑使用？需要安装 Node.js + 登录 QQ，然后把整个 AutoQQ 文件夹复制过来即可",
                 bg="#E3F2FD", fg="#1565C0", font=("微软雅黑", 8), wraplength=600, justify=tk.LEFT).pack(padx=8, pady=4)

        # ── 服务控制卡片 ──
        ctrl_card = tk.LabelFrame(main, text=" 服务控制 ", font=("微软雅黑", 11, "bold"),
                                   bg=self.COLORS["card"], fg="#333", padx=12, pady=8)
        ctrl_card.pack(fill=tk.X, pady=(0, 8))

        # PMHQ 状态
        row_s1 = tk.Frame(ctrl_card, bg=self.COLORS["card"])
        row_s1.pack(fill=tk.X, pady=2)
        tk.Label(row_s1, text="QQ 通信桥接 (PMHQ):", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=22, anchor=tk.W).pack(side=tk.LEFT)
        self.pmhq_indicator = tk.Canvas(row_s1, width=12, height=12, bg=self.COLORS["card"],
                                         highlightthickness=0)
        self.pmhq_indicator.pack(side=tk.LEFT)
        self._draw_indicator(self.pmhq_indicator, "gray")
        self.pmhq_label = tk.Label(row_s1, text=" 未启动", bg=self.COLORS["card"],
                                    font=("微软雅黑", 10), fg=self.COLORS["gray"])
        self.pmhq_label.pack(side=tk.LEFT)

        # Bot 状态
        row_s2 = tk.Frame(ctrl_card, bg=self.COLORS["card"])
        row_s2.pack(fill=tk.X, pady=2)
        tk.Label(row_s2, text="Bot 服务:", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=22, anchor=tk.W).pack(side=tk.LEFT)
        self.node_indicator = tk.Canvas(row_s2, width=12, height=12, bg=self.COLORS["card"],
                                         highlightthickness=0)
        self.node_indicator.pack(side=tk.LEFT)
        self._draw_indicator(self.node_indicator, "gray")
        self.node_label = tk.Label(row_s2, text=" 未启动", bg=self.COLORS["card"],
                                    font=("微软雅黑", 10), fg=self.COLORS["gray"])
        self.node_label.pack(side=tk.LEFT)

        # API 状态
        row_s3 = tk.Frame(ctrl_card, bg=self.COLORS["card"])
        row_s3.pack(fill=tk.X, pady=2)
        tk.Label(row_s3, text="API 接口:", bg=self.COLORS["card"],
                 font=("微软雅黑", 10), width=22, anchor=tk.W).pack(side=tk.LEFT)
        self.api_indicator = tk.Canvas(row_s3, width=12, height=12, bg=self.COLORS["card"],
                                        highlightthickness=0)
        self.api_indicator.pack(side=tk.LEFT)
        self._draw_indicator(self.api_indicator, "gray")
        self.api_label = tk.Label(row_s3, text=" 未就绪", bg=self.COLORS["card"],
                                   font=("微软雅黑", 10), fg=self.COLORS["gray"])
        self.api_label.pack(side=tk.LEFT)

        # 按钮行
        btn_frame = tk.Frame(ctrl_card, bg=self.COLORS["card"])
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        self.start_btn = tk.Button(btn_frame, text="▶  启动 Bot 服务",
                                    command=self.start_server,
                                    bg=self.COLORS["green"], fg="white",
                                    font=("微软雅黑", 11, "bold"),
                                    relief=tk.FLAT, cursor="hand2", padx=16, pady=6)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_btn = tk.Button(btn_frame, text="■  停止 Bot 服务",
                                   command=self.stop_server,
                                   bg=self.COLORS["red"], fg="white",
                                   font=("微软雅黑", 11, "bold"),
                                   relief=tk.FLAT, cursor="hand2", padx=16, pady=6,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.open_filter_btn = tk.Button(btn_frame, text="📋 打开筛选工具",
                                          command=self.open_filter,
                                          bg=self.COLORS["blue"], fg="white",
                                          font=("微软雅黑", 11, "bold"),
                                          relief=tk.FLAT, cursor="hand2", padx=16, pady=6,
                                          state=tk.DISABLED)
        self.open_filter_btn.pack(side=tk.LEFT, padx=(0, 8))

        # ── 日志区域 ──
        log_card = tk.LabelFrame(main, text=" 运行日志 ", font=("微软雅黑", 11, "bold"),
                                  bg=self.COLORS["card"], fg="#333", padx=8, pady=4)
        log_card.pack(fill=tk.BOTH, expand=True)

        log_frame = tk.Frame(log_card, bg="#1e1e1e")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white",
                                 font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
                                 padx=8, pady=6)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部提示
        self.tip_var = tk.StringVar(value="第一步：点击「启动 Bot 服务」 → 第二步：点击「打开筛选工具」")
        tip_bar = tk.Label(self.root, textvariable=self.tip_var, bg="#E8EAF6",
                           fg="#283593", font=("微软雅黑", 9), pady=4)
        tip_bar.pack(fill=tk.X, padx=10, pady=(0, 8))

    def _draw_indicator(self, canvas, color):
        """在 Canvas 上画彩色圆点"""
        canvas.delete("all")
        colors = {
            "green": "#4CAF50", "red": "#F44336", "orange": "#FF9800",
            "gray": "#BDBDBD", "blue": "#2196F3"
        }
        canvas.create_oval(1, 1, 11, 11, fill=colors.get(color, "#BDBDBD"), outline="")

    # ── 环境检测 ─────────────────────────────────────────

    def _auto_check_env(self):
        """自动检测环境"""
        threading.Thread(target=self._check_env_thread, daemon=True).start()

    def _check_env_thread(self):
        # Node.js
        ok, ver = check_nodejs()
        if ok:
            self.queue.put(("nodejs_ok", ver))
        else:
            self.queue.put(("nodejs_fail", ver))

        # QQ
        if check_qq_running():
            self.queue.put(("qq_ok", ""))
        else:
            self.queue.put(("qq_fail", ""))

        # Bot 框架文件
        if LLBOT_DIR.exists() and (LLBOT_DIR / "llbot.js").exists():
            self.queue.put(("botfile_ok", ""))
        else:
            self.queue.put(("botfile_fail", ""))

        # PMHQ 文件
        pmhq_exe = PMHQ_DIR / "pmhq-win-x64.exe"
        if PMHQ_DIR.exists() and pmhq_exe.exists():
            self.queue.put(("pmhqfile_ok", ""))
        else:
            self.queue.put(("pmhqfile_fail", ""))

        # 检查已运行的服务
        if check_pmhq_running():
            self.queue.put(("status_pmhq", "运行中"))
        if check_node_running():
            self.queue.put(("status_node", "运行中"))
        if check_api_ready()[0]:
            self.queue.put(("status_api", "就绪"))
            self.queue.put(("all_ready", True))

    def _periodic_check_qq(self):
        """每 5 秒重新检测 QQ 和 PMHQ 桥接状态"""
        # QQ 进程检测
        if check_qq_running():
            self.qq_status.config(text="已运行", fg=self.COLORS["green"])
        else:
            self.qq_status.config(text="未检测到运行", fg=self.COLORS["orange"])

        # PMHQ 桥接健康检测：如果之前标记为运行中但端口 13000 消失了，则桥接已崩溃
        current_pmhq_label = self.pmhq_label.cget("text").strip()
        if ("运行中" in current_pmhq_label or "注入" in current_pmhq_label) and not port_in_use(13000):
            self._append_log("[警告] PMHQ 桥接已断开！端口 13000 无响应，请重新启动服务")
            self._draw_indicator(self.pmhq_indicator, "red")
            self.pmhq_label.config(text=" 已断开", fg=self.COLORS["red"])
            self._draw_indicator(self.api_indicator, "red")
            self.api_label.config(text=" 不可用", fg=self.COLORS["red"])
            # 桥接断开时禁用筛选按钮，防止用户点击后超时
            self.open_filter_btn.config(state=tk.DISABLED, bg="#9E9E9E")
            self.tip_var.set("PMHQ 桥接已断开！请点击「停止」后重新「启动」")

        self.root.after(5000, self._periodic_check_qq)

    # ── 队列轮询 ─────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "log":
                    self._append_log(msg[1])

                elif msg_type == "error":
                    self._append_log(f"[错误] {msg[1]}")
                    messagebox.showerror("错误", msg[1])
                    self._reset_all_status()

                elif msg_type == "nodejs_ok":
                    self.nodejs_status.config(text=f"已安装 ({msg[1]})", fg=self.COLORS["green"])
                    self.nodejs_install_btn.pack_forget()

                elif msg_type == "nodejs_fail":
                    self.nodejs_status.config(text="未安装", fg=self.COLORS["red"])
                    self.nodejs_install_btn.pack(side=tk.LEFT, padx=(5, 0))
                    self._append_log("[警告] 未检测到 Node.js，请先安装 Node.js")

                elif msg_type == "qq_ok":
                    self.qq_status.config(text="已运行", fg=self.COLORS["green"])

                elif msg_type == "qq_fail":
                    self.qq_status.config(text="未检测到运行", fg=self.COLORS["orange"])

                elif msg_type == "botfile_ok":
                    self.botfile_status.config(text="正常", fg=self.COLORS["green"])

                elif msg_type == "botfile_fail":
                    self.botfile_status.config(text="文件缺失", fg=self.COLORS["red"])

                elif msg_type == "pmhqfile_ok":
                    self.pmhqfile_status.config(text="正常", fg=self.COLORS["green"])

                elif msg_type == "pmhqfile_fail":
                    self.pmhqfile_status.config(text="文件缺失", fg=self.COLORS["red"])

                elif msg_type == "status_pmhq":
                    status = msg[1]
                    if status == "启动中":
                        self._draw_indicator(self.pmhq_indicator, "orange")
                        self.pmhq_label.config(text=" 启动中...", fg=self.COLORS["orange"])
                    elif status == "运行中":
                        self._draw_indicator(self.pmhq_indicator, "green")
                        self.pmhq_label.config(text=" 运行中", fg=self.COLORS["green"])

                elif msg_type == "status_node":
                    status = msg[1]
                    if status == "启动中":
                        self._draw_indicator(self.node_indicator, "orange")
                        self.node_label.config(text=" 启动中...", fg=self.COLORS["orange"])
                    elif status == "运行中":
                        self._draw_indicator(self.node_indicator, "green")
                        self.node_label.config(text=" 运行中", fg=self.COLORS["green"])

                elif msg_type == "tip":
                    self.tip_var.set(msg[1])

                elif msg_type == "status_api":
                    status = msg[1]
                    if status == "等待中":
                        self._draw_indicator(self.api_indicator, "orange")
                        self.api_label.config(text=" 等待中...", fg=self.COLORS["orange"])
                    elif status == "验证中":
                        self._draw_indicator(self.api_indicator, "blue")
                        self.api_label.config(text=" 验证中...", fg=self.COLORS["blue"])
                    elif status == "就绪":
                        self._draw_indicator(self.api_indicator, "green")
                        self.api_label.config(text=" 就绪", fg=self.COLORS["green"])
                    elif status == "就绪(慢)":
                        self._draw_indicator(self.api_indicator, "orange")
                        self.api_label.config(text=" 就绪(较慢)", fg=self.COLORS["orange"])
                    elif status.startswith("超时"):
                        self._draw_indicator(self.api_indicator, "orange")
                        self.api_label.config(text=f" {status}", fg=self.COLORS["orange"])

                elif msg_type == "all_ready":
                    self.all_ready = True
                    self.start_btn.config(state=tk.DISABLED, bg="#9E9E9E")
                    self.stop_btn.config(state=tk.NORMAL)
                    self.open_filter_btn.config(state=tk.NORMAL)
                    self.tip_var.set("服务已就绪！点击「打开筛选工具」开始使用")

        except Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _reset_all_status(self):
        """重置所有状态"""
        self.all_ready = False
        self.start_btn.config(state=tk.NORMAL, bg=self.COLORS["green"])
        self.stop_btn.config(state=tk.DISABLED)
        self.open_filter_btn.config(state=tk.DISABLED)
        self._draw_indicator(self.pmhq_indicator, "gray")
        self.pmhq_label.config(text=" 未启动", fg=self.COLORS["gray"])
        self._draw_indicator(self.node_indicator, "gray")
        self.node_label.config(text=" 未启动", fg=self.COLORS["gray"])
        self._draw_indicator(self.api_indicator, "gray")
        self.api_label.config(text=" 未就绪", fg=self.COLORS["gray"])
        self.tip_var.set("第一步：点击「启动 Bot 服务」 → 第二步：点击「打开筛选工具」")

    # ── 服务控制 ─────────────────────────────────────────

    def start_server(self):
        """启动 Bot 服务"""
        # 检查环境
        ok, _ = check_nodejs()
        if not ok:
            messagebox.showerror("环境错误",
                                  "未检测到 Node.js 运行环境！\n\n"
                                  "请先安装 Node.js，然后重启本程序。\n"
                                  "下载地址: https://nodejs.org/")
            return

        if not LLBOT_DIR.exists():
            messagebox.showerror("文件缺失",
                                  f"找不到 Bot 框架目录:\n{LLBOT_DIR}\n\n"
                                  "请确认 AutoQQ 文件夹完整。")
            return

        pmhq_exe = PMHQ_DIR / "pmhq-win-x64.exe"
        if not pmhq_exe.exists():
            messagebox.showerror("文件缺失",
                                  f"找不到 PMHQ 桥接程序:\n{pmhq_exe}\n\n"
                                  "请从 https://github.com/linyuchen/PMHQ/releases 下载\n"
                                  "并将 pmhq-win-x64.exe 放到 rbt/bin/pmhq/ 目录")
            return

        self._append_log("正在启动 Bot 服务...")
        self.start_btn.config(state=tk.DISABLED, bg="#9E9E9E")
        self.tip_var.set("正在启动服务，请稍候...")

        self.server_thread = ServerStarter(self.queue, {})
        self.server_thread.start()

    def stop_server(self):
        """停止 Bot 服务"""
        if self.server_thread:
            self.server_thread.stop()
        else:
            # 手动清理
            subprocess.run(
                ["taskkill", "/f", "/im", "pmhq-win-x64.exe"],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            subprocess.run(
                ["taskkill", "/f", "/im", "node.exe"],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
            )

        self._append_log("服务已停止")
        self._reset_all_status()

    # ── 打开其他工具 ─────────────────────────────────────

    def open_filter(self):
        """打开筛选工具（优先使用打包的 exe）"""
        # PyInstaller 打包后优先调用 exe，否则用 python 运行 py
        exe_path = BASE_DIR / "qq_gui.exe"
        py_path = BASE_DIR / "qq_gui.py"

        if exe_path.exists():
            subprocess.Popen(
                [str(exe_path)],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._append_log("已启动筛选工具")
        elif py_path.exists():
            subprocess.Popen(
                ["python", str(py_path)],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._append_log("已启动筛选工具")
        else:
            messagebox.showerror("错误", f"找不到筛选工具:\n{py_path}")

    def _open_nodejs_download(self):
        """打开 Node.js 下载页"""
        import webbrowser
        webbrowser.open("https://nodejs.org/zh-cn/")
        self._append_log("已在浏览器打开 Node.js 中文官网下载页")

    # ── 日志 ─────────────────────────────────────────────

    def _append_log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ── 关闭处理 ─────────────────────────────────────────

    def _on_close(self):
        """窗口关闭时询问是否停止服务"""
        if check_node_running():
            result = messagebox.askyesno("确认退出",
                                          "Bot 服务仍在运行中，是否停止服务并退出？\n\n"
                                          "选择「是」：停止服务并退出\n"
                                          "选择「否」：服务继续后台运行，仅关闭启动器")
            if result:
                self.stop_server()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._append_log("AutoQQ 启动器已就绪")
        self._append_log("正在检测运行环境...")
        self.root.mainloop()


# ─── 入口 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Windows 下设置任务栏图标为独立应用
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("autoqq.launcher")
        except Exception:
            pass
    AutoQQLauncher().run()

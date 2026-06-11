#!/usr/bin/env python3
"""
QQ好友/群成员筛选 - 图形化界面
通过 rbt OneBot HTTP API 获取数据并筛选
"""

import json
import re
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from queue import Queue, Empty

import tkinter as tk
from tkinter import ttk, messagebox, filedialog


# ─── 核心筛选逻辑 ────────────────────────────────────────────

class QQFilter:
    def __init__(self, api_url="http://127.0.0.1:8099/", token=None, timeout=30):
        self.api_url = api_url.rstrip("/") + "/"
        self.token = token
        self.timeout = timeout
        self.results = []
        self.log_queue = None

    def _log(self, msg):
        if self.log_queue:
            self.log_queue.put(("log", msg))

    def _api_call(self, action, params=None):
        url = self.api_url + action
        data = json.dumps(params or {}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            self._log(f"[错误] 无法连接到 rbt API: {e}")
            return None
        except Exception as e:
            self._log(f"[错误] API 调用失败 ({action}): {e}")
            return None
        if isinstance(result, dict):
            if result.get("status") == "ok":
                return result.get("data")
            elif result.get("status") == "failed":
                self._log(f"[警告] API 返回失败 ({action}): {result.get('msg', '未知错误')}")
                return None
        return result

    def get_group_list_only(self):
        """仅获取群列表（不含成员详情），速度快"""
        return self._api_call("get_group_list") or []

    def get_friends(self):
        self._log("[1/3] 正在获取好友列表...")
        friend_list = self._api_call("get_friend_list")
        if not friend_list:
            self._log("  好友列表为空或获取失败")
            return
        self._log(f"  获取到 {len(friend_list)} 个好友，正在查询详细信息...")
        count = 0
        for friend in friend_list:
            user_id = friend.get("user_id")
            nickname = friend.get("nickname", "")
            remark = friend.get("remark", "")
            info = self._api_call("get_stranger_info", {"user_id": user_id})
            if info:
                sex = info.get("sex", "unknown")
                age = info.get("age", 0)
                name = remark or nickname
                self.results.append((user_id, name, "好友", sex, age))
                count += 1
            time.sleep(0.3)
        self._log(f"  好友查询完成，共 {count}/{len(friend_list)}")

    def get_group_members_for_groups(self, selected_groups):
        """获取指定群的成员并查询详细信息"""
        total = 0
        for g_idx, (group_id, group_name) in enumerate(selected_groups):
            self._log(f"[群 {g_idx+1}/{len(selected_groups)}] {group_name} - 正在获取成员列表...")
            members = self._api_call("get_group_member_list", {"group_id": group_id})
            if not members:
                self._log(f"  成员列表为空")
                continue
            self._log(f"  共 {len(members)} 人，正在查询性别年龄...")
            for m in members:
                uid = m.get("user_id")
                nick = m.get("nickname", "")
                card = m.get("card", "")
                info = self._api_call("get_stranger_info", {"user_id": uid})
                if info:
                    sex = info.get("sex", "unknown")
                    age = info.get("age", 0)
                else:
                    sex = m.get("sex", "unknown")
                    age = m.get("age", 0)
                name = card or nick
                self.results.append((uid, name, f"群[{group_name}]", sex, age))
                total += 1
            time.sleep(0.3)
        self._log(f"  群成员查询完成，共 {total} 人")

    def filter_results(self, sex=None, age=None, min_age=None, max_age=None):
        sex_map = {"male": "male", "female": "female", "男": "male", "女": "female",
                   "未知": "unknown", "unknown": "unknown"}
        filtered = []
        for qq, name, source, s, a in self.results:
            if sex is not None and s != sex_map.get(sex, sex):
                continue
            if age is not None and a != age:
                continue
            if min_age is not None and a < min_age:
                continue
            if max_age is not None and a > max_age:
                continue
            filtered.append((qq, name, source, s, a))
        return filtered


# ─── GUI ─────────────────────────────────────────────────────────

class QQFilterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QQ 好友/群成员筛选工具")
        self.root.geometry("950x700")
        self.root.minsize(800, 550)
        self.root.configure(bg="#f0f0f0")

        self.queue = Queue()
        self.is_running = False
        self.all_results = []
        self.filtered_results = []
        self.group_list_data = []  # [(group_id, group_name, member_count), ...]

        self._build_ui()
        self._poll_queue()

    # ── UI 构建 ──────────────────────────────────────────────

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#2196F3", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="QQ 好友/群成员筛选工具",
                 bg="#2196F3", fg="white", font=("微软雅黑", 16, "bold"), pady=10).pack()

        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── 左栏 ──
        left = tk.LabelFrame(main_frame, text=" 筛选条件 ", font=("微软雅黑", 11, "bold"),
                             bg="#ffffff", fg="#333", padx=10, pady=10)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        # API
        tk.Label(left, text="API 地址:", bg="#fff", font=("微软雅黑", 9)).pack(anchor=tk.W)
        self.api_var = tk.StringVar(value="http://127.0.0.1:8099/")
        tk.Entry(left, textvariable=self.api_var, width=26, font=("Consolas", 9)).pack(fill=tk.X, pady=(0, 6))

        # 性别
        tk.Label(left, text="性别:", bg="#fff", font=("微软雅黑", 9)).pack(anchor=tk.W)
        sex_frame = tk.Frame(left, bg="#fff")
        sex_frame.pack(fill=tk.X, pady=(0, 6))
        self.sex_var = tk.StringVar(value="不限")
        for label, val in [("不限", "不限"), ("男", "男"), ("女", "女")]:
            tk.Radiobutton(sex_frame, text=label, variable=self.sex_var, value=val,
                           bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 8))

        # 年龄
        tk.Label(left, text="年龄:", bg="#fff", font=("微软雅黑", 9)).pack(anchor=tk.W)
        self.age_mode = tk.StringVar(value="range")
        age_frame = tk.Frame(left, bg="#fff")
        age_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Radiobutton(age_frame, text="范围", variable=self.age_mode, value="range",
                       bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.age_min_var = tk.StringVar(value="18")
        tk.Entry(age_frame, textvariable=self.age_min_var, width=4, font=("微软雅黑", 9)).pack(side=tk.LEFT)
        tk.Label(age_frame, text=" ~ ", bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
        self.age_max_var = tk.StringVar(value="25")
        tk.Entry(age_frame, textvariable=self.age_max_var, width=4, font=("微软雅黑", 9)).pack(side=tk.LEFT)

        age_frame2 = tk.Frame(left, bg="#fff")
        age_frame2.pack(fill=tk.X, pady=(0, 3))
        tk.Radiobutton(age_frame2, text="精确", variable=self.age_mode, value="exact",
                       bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.age_exact_var = tk.StringVar(value="20")
        tk.Entry(age_frame2, textvariable=self.age_exact_var, width=4, font=("微软雅黑", 9)).pack(side=tk.LEFT)
        tk.Label(age_frame2, text="岁", bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT)

        age_frame3 = tk.Frame(left, bg="#fff")
        age_frame3.pack(fill=tk.X, pady=(0, 6))
        tk.Radiobutton(age_frame3, text="不限", variable=self.age_mode, value="none",
                       bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT)

        # 好友
        tk.Label(left, text="数据来源:", bg="#fff", font=("微软雅黑", 9)).pack(anchor=tk.W)
        src_frame = tk.Frame(left, bg="#fff")
        src_frame.pack(fill=tk.X, pady=(0, 6))
        self.include_friends = tk.BooleanVar(value=True)
        tk.Checkbutton(src_frame, text="好友", variable=self.include_friends,
                       bg="#fff", font=("微软雅黑", 9)).pack(side=tk.LEFT)

        # ── 群选择区域 ──
        tk.Label(left, text="选择群 (可多选):", bg="#fff", font=("微软雅黑", 9, "bold")).pack(anchor=tk.W)

        group_btn_frame = tk.Frame(left, bg="#fff")
        group_btn_frame.pack(fill=tk.X, pady=(2, 4))
        self.load_group_btn = tk.Button(group_btn_frame, text="加载群列表",
                                        command=self.load_group_list,
                                        bg="#FF9800", fg="white",
                                        font=("微软雅黑", 9), relief=tk.FLAT, cursor="hand2")
        self.load_group_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.select_all_var = tk.BooleanVar(value=True)
        tk.Checkbutton(group_btn_frame, text="全选", variable=self.select_all_var,
                       bg="#fff", font=("微软雅黑", 9),
                       command=self._toggle_select_all).pack(side=tk.LEFT)

        # 群列表 Listbox（多选）
        list_frame = tk.Frame(left, bg="#fff")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.group_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE,
                                         font=("微软雅黑", 9), height=6,
                                         yscrollcommand=list_scroll.set,
                                         exportselection=False)
        list_scroll.config(command=self.group_listbox.yview)
        self.group_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.group_count_var = tk.StringVar(value="尚未加载群列表")
        tk.Label(left, textvariable=self.group_count_var, bg="#fff",
                 font=("微软雅黑", 9), fg="#999").pack(anchor=tk.W, pady=(0, 4))

        # 按钮
        btn_frame = tk.Frame(left, bg="#fff")
        btn_frame.pack(fill=tk.X, pady=(4, 0))
        self.start_btn = tk.Button(btn_frame, text="开始筛选",
                                   command=self.start_filter,
                                   bg="#4CAF50", fg="white",
                                   font=("微软雅黑", 11, "bold"),
                                   relief=tk.FLAT, cursor="hand2", padx=20, pady=5)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.export_btn = tk.Button(btn_frame, text="导出结果",
                                    command=self.export_results,
                                    bg="#2196F3", fg="white",
                                    font=("微软雅黑", 9),
                                    relief=tk.FLAT, cursor="hand2",
                                    state=tk.DISABLED, padx=10, pady=5)
        self.export_btn.pack(side=tk.LEFT)

        self.stats_var = tk.StringVar(value="")
        tk.Label(left, textvariable=self.stats_var, bg="#fff",
                 font=("微软雅黑", 9), fg="#666").pack(anchor=tk.W, pady=(6, 0))

        # ── 右栏 ──
        right = tk.Frame(main_frame, bg="#f0f0f0")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 日志页
        log_tab = tk.Frame(self.notebook, bg="#1e1e1e")
        self.notebook.add(log_tab, text=" 日志 ")
        self.log_text = tk.Text(log_tab, bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
                                font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
                                padx=8, pady=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 结果页
        result_tab = tk.Frame(self.notebook, bg="#fff")
        self.notebook.add(result_tab, text=" 结果 ")
        columns = ("QQ号", "昵称", "来源", "性别", "年龄")
        self.tree = ttk.Treeview(result_tab, columns=columns, show="headings", height=20)
        col_widths = [140, 180, 220, 60, 60]
        for col, w in zip(columns, col_widths):
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=w, anchor=tk.CENTER)
        self.tree.column("昵称", anchor=tk.W)
        self.tree.column("来源", anchor=tk.W)
        tree_sy = ttk.Scrollbar(result_tab, orient=tk.VERTICAL, command=self.tree.yview)
        tree_sx = ttk.Scrollbar(result_tab, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_sy.set, xscrollcommand=tree_sx.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_sy.grid(row=0, column=1, sticky="ns")
        tree_sx.grid(row=1, column=0, sticky="ew")
        result_tab.grid_rowconfigure(0, weight=1)
        result_tab.grid_columnconfigure(0, weight=1)

        # 底部状态
        bottom = tk.Frame(self.root, bg="#f0f0f0")
        bottom.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.status_var = tk.StringVar(value='就绪 - 请先加载群列表，再选择群开始筛选')
        tk.Label(bottom, textvariable=self.status_var, bg="#f0f0f0",
                 font=("微软雅黑", 9), fg="#666").pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=300)
        self.progress.pack(side=tk.RIGHT, padx=(10, 0))

    # ── 群列表操作 ──────────────────────────────────────────

    def load_group_list(self):
        """加载群列表（仅获取群名和人数，不查成员详情）"""
        self.load_group_btn.config(text="加载中...", state=tk.DISABLED)
        thread = threading.Thread(target=self._load_group_list_thread, daemon=True)
        thread.start()

    def _load_group_list_thread(self):
        qf = QQFilter(api_url=self.api_var.get().strip())
        qf.log_queue = self.queue
        self.queue.put(("log", "正在加载群列表..."))
        groups = qf.get_group_list_only()
        if not groups:
            self.queue.put(("error", "无法获取群列表，请检查 rbt 是否运行"))
            self.queue.put(("load_done", []))
            return
        data = [(g.get("group_id"), g.get("group_name", "未知"), g.get("member_count", 0)) for g in groups]
        self.queue.put(("log", f"共 {len(data)} 个群"))
        self.queue.put(("load_done", data))

    def _toggle_select_all(self):
        if self.select_all_var.get():
            self.group_listbox.select_set(0, tk.END)
        else:
            self.group_listbox.selection_clear(0, tk.END)

    # ── 轮询队列 ────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg_type, msg = self.queue.get_nowait()
                if msg_type == "log":
                    self._append_log(msg)
                elif msg_type == "progress":
                    self.status_var.set(msg)
                elif msg_type == "result":
                    self.all_results = msg
                    self._apply_filter_and_show()
                elif msg_type == "done":
                    self._on_done(msg)
                elif msg_type == "error":
                    messagebox.showerror("错误", msg)
                    self._reset_ui()
                elif msg_type == "load_done":
                    self._on_group_list_loaded(msg)
        except Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _on_group_list_loaded(self, data):
        self.group_list_data = data
        self.group_listbox.delete(0, tk.END)
        for gid, name, count in data:
            self.group_listbox.insert(tk.END, f"{name}  ({count}人)")
        self.group_count_var.set(f"共 {len(data)} 个群，已全选")
        self.group_listbox.select_set(0, tk.END)
        self.select_all_var.set(True)
        self.load_group_btn.config(text="刷新群列表", state=tk.NORMAL)
        self.status_var.set(f"已加载 {len(data)} 个群，请选择要筛选的群后点击「开始筛选」")

    def _get_selected_groups(self):
        selected = self.group_listbox.curselection()
        if not selected:
            return [], []
        chosen = [(self.group_list_data[i][0], self.group_list_data[i][1]) for i in selected]
        return selected, chosen

    # ── 开始筛选 ────────────────────────────────────────────

    def start_filter(self):
        do_friends = self.include_friends.get()
        do_groups = len(self.group_listbox.curselection()) > 0

        if not do_friends and not do_groups:
            messagebox.showwarning("提示", "至少选择一个数据来源（好友或群成员）")
            return

        self.is_running = True
        self.start_btn.config(text="正在筛选...", bg="#F44336", state=tk.DISABLED)
        self.load_group_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self._clear_tree()
        self.all_results = []

        sex_val = self.sex_var.get()
        sex = None if sex_val == "不限" else sex_val
        age_mode = self.age_mode.get()
        age = min_age = max_age = None
        if age_mode == "exact":
            try:
                age = int(self.age_exact_var.get())
            except ValueError:
                age = None
        elif age_mode == "range":
            try:
                min_age = int(self.age_min_var.get()) if self.age_min_var.get() else None
            except ValueError:
                min_age = None
            try:
                max_age = int(self.age_max_var.get()) if self.age_max_var.get() else None
            except ValueError:
                max_age = None

        _, selected_groups = self._get_selected_groups()

        thread = threading.Thread(target=self._run_filter, args=(
            self.api_var.get().strip(), sex, age, min_age, max_age,
            do_friends, selected_groups
        ), daemon=True)
        thread.start()

    def _run_filter(self, api_url, sex, age, min_age, max_age, do_friends, selected_groups):
        qf = QQFilter(api_url=api_url)
        qf.log_queue = self.queue
        self.queue.put(("progress", "正在连接 rbt API..."))
        self.queue.put(("log", "=" * 50))
        self.queue.put(("log", f"API: {api_url}"))
        self.queue.put(("log", f"性别: {sex or '不限'}  |  年龄: {self._age_desc(age, min_age, max_age)}"))
        self.queue.put(("log", "=" * 50))

        if do_friends:
            self.queue.put(("progress", "正在获取好友列表..."))
            qf.get_friends()

        if selected_groups:
            self.queue.put(("progress", f"正在查询 {len(selected_groups)} 个群的成员..."))
            qf.get_group_members_for_groups(selected_groups)

        self.queue.put(("progress", f"正在筛选... (共 {len(qf.results)} 条记录)"))
        filtered = qf.filter_results(sex=sex, age=age, min_age=min_age, max_age=max_age)
        self.queue.put(("log", "=" * 50))
        self.queue.put(("log", f"总记录: {len(qf.results)}  |  筛选结果: {len(filtered)} 人"))
        self.queue.put(("log", "=" * 50))
        self.queue.put(("result", filtered))
        self.queue.put(("done", len(filtered)))

    @staticmethod
    def _age_desc(age, min_age, max_age):
        if age is not None:
            return f"{age}岁"
        elif min_age and max_age:
            return f"{min_age}~{max_age}岁"
        elif min_age:
            return f">={min_age}岁"
        elif max_age:
            return f"<={max_age}岁"
        return "不限"

    # ── 结果展示 ────────────────────────────────────────────

    def _apply_filter_and_show(self):
        self._clear_tree()
        self.filtered_results = self.all_results
        sex_label = {"male": "男", "female": "女", "unknown": "未知"}
        for qq, name, source, sex, age in self.filtered_results:
            self.tree.insert("", tk.END, values=(qq, name, source, sex_label.get(sex, sex), f"{age}岁"))
        self.stats_var.set(f"共 {len(self.filtered_results)} 条结果")

    def _on_done(self, count):
        self._reset_ui()
        self.notebook.select(1)

    def _reset_ui(self):
        self.is_running = False
        self.start_btn.config(text="开始筛选", bg="#4CAF50", state=tk.NORMAL)
        self.load_group_btn.config(state=tk.NORMAL)
        self.export_btn.config(state=tk.NORMAL if self.filtered_results else tk.DISABLED)
        self.progress.stop()
        self.status_var.set(f"就绪 - 完成筛选，共 {len(self.filtered_results)} 人")

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _append_log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ── 排序 ────────────────────────────────────────────────

    def _sort_column(self, col):
        col_map = {"QQ号": 0, "昵称": 1, "来源": 2, "性别": 3, "年龄": 4}
        idx = col_map.get(col, 0)
        ascending = self._sort_ascending if hasattr(self, '_sort_ascending') else True
        self._sort_ascending = not ascending
        data = [(self.tree.set(item, col), item) for item in self.tree.get_children("")]
        if idx == 4:
            data.sort(key=lambda x: int(x[0].replace("岁", "")) if x[0].replace("岁", "").isdigit() else 0,
                      reverse=not ascending)
        else:
            data.sort(reverse=not ascending)
        for i, (_, item) in enumerate(data):
            self.tree.move(item, "", i)

    # ── 导出 ────────────────────────────────────────────────

    @staticmethod
    def _clean_filename(name):
        """去掉群名中的表情符号和非文件名字符，只保留中文、字母、数字、常用符号"""
        cleaned = re.sub(r'[^\w\u4e00-\u9fff\s\-_.()（ ）【 】]', '', name, flags=re.UNICODE)
        cleaned = cleaned.strip()
        return cleaned or "qq_group"

    def _get_default_filename(self):
        """根据选中的群生成默认文件名"""
        _, selected = self._get_selected_groups()
        if len(selected) == 1:
            group_name = self._clean_filename(selected[0][1])
            return f"{group_name}.txt"
        return "qq_filter_result.txt"

    def export_results(self):
        if not self.filtered_results:
            messagebox.showwarning("提示", "没有可导出的结果")
            return
        default_name = self._get_default_filename()
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("CSV", "*.csv"), ("所有文件", "*.*")],
            initialfile=default_name
        )
        if not filepath:
            return
        sex_label = {"male": "男", "female": "女", "unknown": "未知"}
        with open(filepath, "w", encoding="utf-8") as f:
            for qq, name, source, sex, age in self.filtered_results:
                sex_cn = sex_label.get(sex, sex)
                f.write(f"{qq}  {name}  {sex_cn}  {age}岁\n")
        self.queue.put(("log", f"[导出] 结果已保存到: {filepath}"))
        self.status_var.set(f"已导出: {filepath}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    QQFilterGUI().run()
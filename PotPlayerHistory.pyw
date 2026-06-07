#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PotPlayer RememberFiles 图形化管理器
支持 UTF-8 / UTF-16 LE / ANSI 等多种编码
"""

import copy
import os
import re
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from pathlib import Path


class RememberFilesManager:
    def __init__(self, root):
        self.root = root
        self.root.title("PotPlayer 播放位置记忆管理器")
        self.root.geometry("980x640")
        self.root.minsize(800, 500)
        self.root.resizable(True, True)

# 窗口图标（Release 模式下可能无效，但保留尝试）
        try:
            import sys
            from pathlib import Path
            if getattr(sys, 'frozen', False):
                base = Path(__file__).parent
            else:
                base = Path(__file__).parent
            ico = base / "logo.ico"
            if ico.exists():
                self.root.iconbitmap(default=str(ico))
        except:
            pass
        # ====================================================================================

        self.config_path = None
        self.entries = []          # [(old_idx, frames, path), ...]
        self.display_entries = []  # 用于显示过滤后的结果
        self.file_encoding = 'utf-8'

        # 撤销功能：保存操作历史（栈结构）
        self.history = []          # 每个元素是 (操作描述, entries副本)

        # 选择历史栈（最多5步）
        self.selection_history = []   # 每个元素是 frozenset of item_ids
        self._recording = False       # 防止程序内部触发时重复入栈

        # 排序相关（序号列不可排序）
        self.sort_column = "修改日期"  # 当前排序列
        self.sort_reverse = False      # False=升序（最旧的在上）

        self.setup_ui()
        self.update_button_states()
        self.auto_detect_config()

    # ──────────────────────────────────────────
    # UI 构建
    # ──────────────────────────────────────────
    def setup_ui(self):
        # ── 顶部：配置文件选择 ──
        top_frame = ttk.Frame(self.root, padding=(8, 6))
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="配置文件:").pack(side=tk.LEFT)
        self.config_var = tk.StringVar()
        self.config_entry = ttk.Entry(top_frame, textvariable=self.config_var)
        self.config_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        ttk.Button(top_frame, text="打开配置文件(O)", command=self.browse_config, width=14).pack(side=tk.LEFT)

        # ── 工具栏：分左右两组，统一间距 ──
        toolbar = ttk.Frame(self.root, padding=(8, 4))
        toolbar.pack(fill=tk.X)

        # 左侧：过滤 + 选择操作
        left_bar = ttk.Frame(toolbar)
        left_bar.pack(side=tk.LEFT)

        self.filter_label = ttk.Label(left_bar, text="排除关键词:")
        self.filter_label.pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add('write', lambda *a: self.apply_filter())
        self.filter_entry = ttk.Entry(left_bar, textvariable=self.filter_var, width=22)
        self.filter_entry.pack(side=tk.LEFT, padx=(4, 2))

        # 模式切换按钮：排除 / 提取
        self.filter_mode = 'exclude'   # 'exclude' | 'include'
        self.btn_filter_mode = ttk.Button(left_bar, text="⇄ 提取", width=6,
                                          command=self.toggle_filter_mode)
        self.btn_filter_mode.pack(side=tk.LEFT, padx=(0, 12))

        self.btn_age          = ttk.Button(left_bar, text="按日期搜索",  command=self.search_by_age,       width=10)
        self.btn_select_all   = ttk.Button(left_bar, text="全选(A)",     command=self.select_all,           width=8)
        self.btn_invert       = ttk.Button(left_bar, text="反选(I)",     command=self.invert_selection,     width=8)
        self.btn_clean_missing= ttk.Button(left_bar, text="清理失效",    command=self.select_missing_files, width=8)
        self.btn_delete       = ttk.Button(left_bar, text="删除选中(Del)", command=self.delete_selected,    width=11)

        for btn in (self.btn_age, self.btn_select_all, self.btn_invert,
                    self.btn_clean_missing, self.btn_delete):
            btn.pack(side=tk.LEFT, padx=3)

        # 右侧：撤销 + 保存
        right_bar = ttk.Frame(toolbar)
        right_bar.pack(side=tk.RIGHT)

        self.btn_undo = ttk.Button(right_bar, text="↩ 撤销(Z)", command=self.undo_last,    width=10)
        self.btn_save = ttk.Button(right_bar, text="保存(S)",    command=self.save_changes, width=8)
        self.btn_undo.pack(side=tk.LEFT, padx=3)
        self.btn_save.pack(side=tk.LEFT, padx=(3, 0))

        # ── 快捷键绑定 ──
        self.root.bind('<Control-o>', lambda e: self.browse_config())
        self.root.bind('<Control-O>', lambda e: self.browse_config())
        self.root.bind('<Control-s>', lambda e: self.save_changes())
        self.root.bind('<Control-S>', lambda e: self.save_changes())
        self.root.bind('<Control-z>', lambda e: self.undo_last())
        self.root.bind('<Control-Z>', lambda e: self.undo_last())
        self.root.bind('<Control-a>', lambda e: self._select_all_if_focused())
        self.root.bind('<Control-A>', lambda e: self._select_all_if_focused())
        self.root.bind('<Control-i>', lambda e: self.invert_selection())
        self.root.bind('<Control-I>', lambda e: self.invert_selection())
        self.root.bind('<Delete>',    lambda e: self._delete_if_tree_focused())

        # ── 状态栏：左侧主信息 + 右侧选择撤销提示 ──
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.sel_undo_var = tk.StringVar(value="")
        sel_undo_label = ttk.Label(status_frame, textvariable=self.sel_undo_var,
                                   relief=tk.SUNKEN, anchor=tk.E, padding=(6, 2), width=18)
        sel_undo_label.pack(side=tk.RIGHT)

        ttk.Separator(status_frame, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(status_frame, textvariable=self.status_var,
                               relief=tk.SUNKEN, anchor=tk.W, padding=(6, 2))
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── 表格区域（Frame 包裹，确保滚动条紧贴表格右侧） ──
        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 2))

        columns = ("序号", "帧数", "文件路径", "修改日期")
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show="headings", selectmode="extended")

        # 列标题（序号列不可排序）
        self.tree.heading("序号",     text="序号")
        self.tree.heading("帧数",     text="帧数位置",
                          command=lambda: self.sort_by_column("帧数"))
        self.tree.heading("文件路径", text="文件路径",
                          command=lambda: self.sort_by_column("文件路径"))
        self.tree.heading("修改日期", text="最后修改时间",
                          command=lambda: self.sort_by_column("修改日期"))

        self.tree.column("序号",     width=58,  minwidth=50,  anchor=tk.CENTER, stretch=False)
        self.tree.column("帧数",     width=100, minwidth=80,  anchor=tk.CENTER, stretch=False)
        self.tree.column("文件路径", width=580, minwidth=200)
        self.tree.column("修改日期", width=155, minwidth=130, anchor=tk.CENTER, stretch=False)

        v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        # grid 布局：表格与纵向滚动条精确对齐
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # 双击预览
        self.tree.bind("<Double-1>", self.show_file_info)

        # 用户手动点击表格前，先记录当前选择状态
        self.tree.bind("<ButtonPress-1>", self._on_tree_click_before)
        self.tree.bind("<<TreeviewSelect>>", self._on_treeview_select)

        # 初始化列标题箭头
        self.update_column_heading()


    # ──────────────────────────────────────────
    # 排序
    # ──────────────────────────────────────────
    def _get_sort_key_func(self):
        """返回当前排序列对应的 key 函数（用于 data_with_index 列表）"""
        if self.sort_column == "帧数":
            return lambda x: x[1][1]
        elif self.sort_column == "文件路径":
            return lambda x: x[1][2].lower()
        else:  # 修改日期（默认）
            def by_mtime(x):
                path = x[1][2]
                try:
                    return datetime.fromtimestamp(os.path.getmtime(path))
                except OSError:
                    return datetime.min
            return by_mtime

    def _sorted_display(self):
        """返回排序后的 [(orig_idx, entry), ...] 列表"""
        data = list(enumerate(self.display_entries))
        data.sort(key=self._get_sort_key_func(), reverse=self.sort_reverse)
        return data

    def sort_by_column(self, col):
        """切换排序列"""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self.refresh_table()
        self.update_column_heading()

    def update_column_heading(self):
        """更新列标题，显示当前排序箭头"""
        arrow = " v" if self.sort_reverse else " ^"
        col_texts = {
            "帧数":     "帧数位置",
            "文件路径": "文件路径",
            "修改日期": "最后修改时间",
        }
        self.tree.heading("序号", text="序号")
        for col, label in col_texts.items():
            text = f"{label}{arrow}" if col == self.sort_column else label
            self.tree.heading(col, text=text)

    # ──────────────────────────────────────────
    # 按钮状态 & 历史
    # ──────────────────────────────────────────
    def update_button_states(self):
        has_config = bool(self.config_path and self.entries)
        state = "normal" if has_config else "disabled"
        for btn in (self.btn_age, self.btn_delete, self.btn_select_all,
                    self.btn_invert, self.btn_clean_missing, self.btn_save):
            btn.config(state=state)
        # 撤销按钮：有选中行 or 有数据历史 都可用
        has_selection = bool(self.tree.selection()) if hasattr(self, 'tree') else False
        undo_ok = bool(self.selection_history) or bool(self.history) or has_selection
        self.btn_undo.config(state="normal" if undo_ok else "disabled")

    def _push_selection(self, snapshot: frozenset):
        """将选择快照压入历史栈（最多保留5步，相邻重复不入栈）"""
        if self.selection_history and self.selection_history[-1] == snapshot:
            return
        self.selection_history.append(snapshot)
        if len(self.selection_history) > 5:
            self.selection_history.pop(0)
        self._update_sel_undo_hint()

    def _finish_undo_selection(self):
        """撤销选择完成后，等所有延迟事件处理完再解除录制锁"""
        self._recording = False
        # 同步 _sel_before_click，避免下次点击用到过期的快照
        self._sel_before_click = frozenset(self.tree.selection())

    def _on_tree_click_before(self, event=None):
        """鼠标按下前记录当前选择状态，供 <<TreeviewSelect>> 入栈用"""
        if not self._recording:
            self._sel_before_click = frozenset(self.tree.selection())

    def _on_treeview_select(self, event=None):
        """用户手动点击导致选择变化后，把点击前的状态入栈"""
        if self._recording:
            return
        before = getattr(self, '_sel_before_click', frozenset())
        after  = frozenset(self.tree.selection())
        if before != after:
            self._push_selection(before)
        self.update_button_states()

    def _set_selection_programmatic(self, items):
        """程序内部设置选择：先把当前状态入栈，再执行选择"""
        before = frozenset(self.tree.selection())
        self._recording = True
        self.tree.selection_set(items)
        self._recording = False
        after = frozenset(self.tree.selection())
        if before != after:
            self._push_selection(before)   # 存的是操作【前】的状态
        self.update_button_states()

    def _clear_selection_programmatic(self):
        """程序内部清空选择，不入栈（用于刷新表格等场景）"""
        self._recording = True
        self.tree.selection_remove(self.tree.selection())
        self._recording = False

    def _update_sel_undo_hint(self):
        """更新状态栏右侧的选择撤销步数提示"""
        n = len(self.selection_history)
        if n > 0:
            self.sel_undo_var.set(f"可撤销选择: {n} 步")
        else:
            self.sel_undo_var.set("")

    def save_to_history(self, description):
        snapshot = copy.deepcopy(self.entries)
        self.history.append((description, snapshot))
        if len(self.history) > 50:
            self.history.pop(0)
        self.update_button_states()
        self.status_var.set(f"[已记录] {description} (可撤销)")

    def undo_last(self):
        """Ctrl+Z：有选择历史时撤销选择；否则撤销数据操作"""
        # ── 优先：撤销选择 ──
        if self.selection_history:
            prev = self.selection_history.pop()
            valid = [i for i in prev if i in self.tree.get_children()]
            self._recording = True
            self.tree.selection_set(valid)
            # after_idle 确保所有延迟事件（<<TreeviewSelect>> 等）都在 _recording=True 期间被屏蔽
            self.root.after_idle(self._finish_undo_selection)
            n = len(self.selection_history)
            self.status_var.set(f"[撤销选择] 还可撤销 {n} 步" if n else "[撤销选择] 已到最早一步")
            self._update_sel_undo_hint()
            self.update_button_states()
            return

        # ── 其次：撤销数据操作 ──
        if not self.history:
            messagebox.showinfo("提示", "没有可以撤销的操作了")
            return
        desc, snapshot = self.history.pop()
        self.entries = snapshot
        self.display_entries = self.entries.copy()
        self.filter_var.set("")
        self.refresh_table()
        self.update_button_states()
        self.status_var.set(f"[撤销] {desc}")

    # ──────────────────────────────────────────
    # 文件读写
    # ──────────────────────────────────────────
    def detect_encoding(self, filepath):
        for enc in ('utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be', 'gbk', 'gb2312', 'latin-1'):
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    f.read()
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return 'latin-1'

    def auto_detect_config(self):
        """启动时自动查找同目录下的 PotPlayer ini 配置文件"""
        import sys
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent

        # PotPlayer 常见配置文件名关键词（按优先级排列）
        keywords = ['PotPlayerMini64', 'PotPlayerMini', 'PotPlayer64', 'PotPlayer']
        candidates = []
        for f in base.glob('*.ini'):
            for priority, kw in enumerate(keywords):
                if kw.lower() in f.name.lower():
                    candidates.append((priority, f))
                    break

        if not candidates:
            # 没找到，保持就绪状态等用户手动打开
            return

        # 按优先级排序，取最优先的那个
        candidates.sort(key=lambda x: x[0])
        found = candidates[0][1]

        self.config_var.set(str(found))
        self.load_config()
        self.status_var.set(
            f"[自动加载] {found.name} | {len(self.entries)} 条记录 | 编码: {self.file_encoding}"
        )

    def browse_config(self):
        filepath = filedialog.askopenfilename(
            title="选择 PotPlayer 配置文件",
            filetypes=[("INI 文件", "*.ini"), ("DPL 文件", "*.dpl"), ("所有文件", "*.*")]
        )
        if filepath:
            self.config_var.set(filepath)
            self.load_config()

    def load_config(self):
        self.config_path = Path(self.config_var.get())
        if not self.config_path.exists():
            messagebox.showerror("错误", f"文件不存在:\n{self.config_path}")
            return
        try:
            self.file_encoding = self.detect_encoding(self.config_path)
            with open(self.config_path, 'r', encoding=self.file_encoding) as f:
                content = f.read()
            self.entries = self.parse_remember_files(content)
            self.display_entries = self.entries.copy()
            self.history = []
            self.refresh_table()
            self.update_button_states()
            self.update_column_heading()
            self.status_var.set(
                f"已加载 {len(self.entries)} 条记录 | 编码: {self.file_encoding}"
            )
        except Exception as e:
            messagebox.showerror("错误", f"读取配置文件失败:\n{e}")

    def parse_remember_files(self, content):
        pattern = re.compile(r'^(\d+)=(\d+)=(.+)$')
        entries = []
        in_section = False
        for line in content.splitlines():
            s = line.strip()
            if s.startswith('[RememberFiles]'):
                in_section = True
                continue
            if in_section and s.startswith('['):
                break
            if in_section and s:
                m = pattern.match(s)
                if m:
                    entries.append((int(m.group(1)), int(m.group(2)), m.group(3)))
        return entries

    def get_file_mtime(self, path):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            return mtime.strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            return "文件不存在"

    # ──────────────────────────────────────────
    # 表格刷新 & 过滤
    # ──────────────────────────────────────────
    def toggle_filter_mode(self):
        if self.filter_mode == 'exclude':
            self.filter_mode = 'include'
            self.filter_label.config(text="提取关键词:")
            self.btn_filter_mode.config(text="⇄ 排除")
        else:
            self.filter_mode = 'exclude'
            self.filter_label.config(text="排除关键词:")
            self.btn_filter_mode.config(text="⇄ 提取")
        self.apply_filter()

    def apply_filter(self):
        keyword = self.filter_var.get().strip().lower()
        if not keyword:
            self.display_entries = self.entries.copy()
            self.status_var.set(f"显示全部 {len(self.entries)} 条记录")
            return

        def matches(e):
            path = e[2].lower()
            if keyword in path:
                return True
            if keyword in "失效" and not os.path.exists(e[2]):
                return True
            return False

        if self.filter_mode == 'exclude':
            self.display_entries = [e for e in self.entries if not matches(e)]
            hidden = len(self.entries) - len(self.display_entries)
            self.status_var.set(
                f"[排除] 已隐藏 {hidden} 条，显示 {len(self.display_entries)} / {len(self.entries)} 条"
            )
        else:
            self.display_entries = [e for e in self.entries if matches(e)]
            self.status_var.set(
                f"[提取] 匹配 {len(self.display_entries)} / {len(self.entries)} 条"
            )
        self.refresh_table()

    def refresh_table(self):
        self._recording = True
        self.tree.delete(*self.tree.get_children())
        self._recording = False
        # 表格重建后 item_id 全部失效，清空选择历史
        self.selection_history.clear()
        self._update_sel_undo_hint()
        for display_idx, (_, (_, frames, path)) in enumerate(self._sorted_display(), 1):
            mtime = self.get_file_mtime(path)
            display_path = f"[失效] {path}" if mtime == "文件不存在" else path
            self.tree.insert("", tk.END, values=(display_idx, frames, display_path, mtime))

    def get_selected_indices(self):
        """返回选中行在 display_entries 中的原始索引列表"""
        selected_items = self.tree.selection()
        if not selected_items:
            return []
        sorted_data = self._sorted_display()
        indices = set()
        for item in selected_items:
            values = self.tree.item(item, "values")
            if not values:
                continue
            try:
                display_idx = int(values[0]) - 1
                if 0 <= display_idx < len(sorted_data):
                    indices.add(sorted_data[display_idx][0])
            except (ValueError, IndexError):
                pass
        return sorted(indices)

    # ──────────────────────────────────────────
    # 操作：选择、删除、搜索
    # ──────────────────────────────────────────
    def _is_typing(self):
        """当前焦点是否在输入框（避免快捷键干扰打字）"""
        w = self.root.focus_get()
        return isinstance(w, (tk.Entry, ttk.Entry))

    def _select_all_if_focused(self):
        """Ctrl+A：输入框内保持默认全选文字行为，否则全选表格"""
        if not self._is_typing():
            self.select_all()

    def _delete_if_tree_focused(self):
        """Del：只要焦点不在输入框内就触发删除"""
        if not self._is_typing():
            self.delete_selected()

    def select_all(self):
        self._set_selection_programmatic(self.tree.get_children())
        self.status_var.set(f"已全选 {len(self.tree.get_children())} 条记录")

    def invert_selection(self):
        selected = set(self.tree.selection())
        new_sel = [i for i in self.tree.get_children() if i not in selected]
        self._set_selection_programmatic(new_sel)
        self.status_var.set("已反选")

    def _select_by_orig_indices(self, target_orig_indices, label):
        """根据原始索引集合选中对应行，并滚动到第一条"""
        target_set = set(target_orig_indices)
        sorted_data = self._sorted_display()
        all_items = self.tree.get_children()
        to_select = []
        first_item = None
        for display_idx, (orig_idx, _) in enumerate(sorted_data):
            if orig_idx in target_set:
                item_id = all_items[display_idx]
                to_select.append(item_id)
                if first_item is None:
                    first_item = item_id
        self._set_selection_programmatic(to_select)
        if first_item:
            self.tree.see(first_item)
        self.status_var.set(f"[搜索] 已选中 {len(target_orig_indices)} 条{label}")

    def search_by_age(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("按日期搜索")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示（等窗口渲染后再计算）
        def center_dialog():
            dialog.update_idletasks()
            rw = self.root.winfo_x() + self.root.winfo_width() // 2
            rh = self.root.winfo_y() + self.root.winfo_height() // 2
            dw, dh = dialog.winfo_width(), dialog.winfo_height()
            dialog.geometry(f"+{rw - dw // 2}+{rh - dh // 2}")
        dialog.after(0, center_dialog)

        outer = ttk.Frame(dialog, padding=(20, 16, 20, 16))
        outer.pack(fill=tk.BOTH, expand=True)

        # ── 标题 ──
        ttk.Label(outer, text="搜索在此日期之前播放的记录：").pack(pady=(0, 12))

        # ── 日期行 ──
        date_frame = ttk.Frame(outer)
        date_frame.pack()

        default_date = datetime.now() - timedelta(days=90)
        year_var  = tk.StringVar(value=str(default_date.year))
        month_var = tk.StringVar(value=str(default_date.month))
        day_var   = tk.StringVar(value=str(default_date.day))
        max_year  = datetime.now().year + 10

        ttk.Spinbox(date_frame, from_=2000, to=max_year, width=6,
                    textvariable=year_var).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" 年").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Spinbox(date_frame, from_=1, to=12, width=4,
                    textvariable=month_var).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" 月").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Spinbox(date_frame, from_=1, to=31, width=4,
                    textvariable=day_var).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" 日").pack(side=tk.LEFT)

        # ── 分隔线 ──
        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(14, 10))

        # ── 快捷选择：标签 + 两行按钮（grid 布局） ──
        ttk.Label(outer, text="快捷选择：").pack(anchor=tk.W)

        quick_frame = ttk.Frame(outer)
        quick_frame.pack(pady=(6, 0))

        def set_days_ago(days):
            t = datetime.now() - timedelta(days=days)
            year_var.set(str(t.year))
            month_var.set(str(t.month))
            day_var.set(str(t.day))

        presets = [("7 天前", 7), ("30 天前", 30), ("90 天前", 90),
                   ("180 天前", 180), ("1 年前", 365)]
        for col, (lbl, days) in enumerate(presets):
            ttk.Button(quick_frame, text=lbl, width=8,
                       command=lambda d=days: set_days_ago(d)
                       ).grid(row=0, column=col, padx=3, pady=2)

        # ── 搜索按钮 ──
        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(14, 10))

        def do_search():
            try:
                cutoff_date = datetime(int(year_var.get()),
                                       int(month_var.get()),
                                       int(day_var.get()))
            except ValueError:
                messagebox.showerror("错误", "请输入有效的日期", parent=dialog)
                return
            if cutoff_date > datetime.now():
                messagebox.showerror("错误", "不能选择未来的日期", parent=dialog)
                return

            matched = []
            for i, (_, _, path) in enumerate(self.display_entries):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if mtime < cutoff_date:
                        matched.append(i)
                except OSError:
                    pass

            if not matched:
                messagebox.showinfo(
                    "搜索结果",
                    f"没有找到 {cutoff_date.strftime('%Y-%m-%d')} 之前播放的记录",
                    parent=dialog
                )
                return

            dialog.destroy()
            self._select_by_orig_indices(
                matched,
                f"{cutoff_date.strftime('%Y-%m-%d')} 之前的记录"
            )

        btn_row = ttk.Frame(outer)
        btn_row.pack()
        ttk.Button(btn_row, text="搜索并选中", command=do_search, width=14).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="取消", command=dialog.destroy, width=8).pack(side=tk.LEFT, padx=4)

    def select_missing_files(self):
        missing = [
            i for i, (_, _, path) in enumerate(self.display_entries)
            if not os.path.exists(path)
        ]
        if not missing:
            messagebox.showinfo("提示", "没有找到文件不存在的记录")
            return
        self._select_by_orig_indices(missing, "条文件不存在的记录")

    def delete_selected(self):
        selected_indices = self.get_selected_indices()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选中要删除的记录（可多选）")
            return

        files_to_delete = [self.display_entries[i][2] for i in selected_indices]
        preview = "\n".join(os.path.basename(f) for f in files_to_delete[:5])
        if len(files_to_delete) > 5:
            preview += f"\n... 共 {len(files_to_delete)} 个文件"

        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除选中的 {len(selected_indices)} 条记录吗？\n\n{preview}\n\n"
            "删除后序号将自动重新排列。"
        ):
            return

        self.save_to_history(f"删除 {len(selected_indices)} 条记录")

        idx_set = set(selected_indices)
        kept = [e for i, e in enumerate(self.display_entries) if i not in idx_set]
        self.entries = kept
        self.display_entries = kept.copy()
        self.refresh_table()
        self.filter_var.set("")
        self.update_button_states()
        self.status_var.set(
            f"已删除 {len(selected_indices)} 条，剩余 {len(self.entries)} 条"
        )

    # ──────────────────────────────────────────
    # 详情 & 保存
    # ──────────────────────────────────────────
    def show_file_info(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if not values:
            return
        try:
            display_idx = int(values[0]) - 1
        except ValueError:
            return

        sorted_data = self._sorted_display()
        if not (0 <= display_idx < len(sorted_data)):
            return

        orig_idx = sorted_data[display_idx][0]
        _, frames, path = self.display_entries[orig_idx]

        info = f"文件: {path}\n\n帧数位置: {frames} 帧"
        try:
            size = os.path.getsize(path) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            info += f"\n文件大小: {size:.2f} MB"
            info += f"\n最后修改: {mtime.strftime('%Y-%m-%d %H:%M:%S')}"
            info += "\n\n提示: 帧数 约等于 播放秒数 x 视频帧率\n如需精确时间，可用 PotPlayer 打开后按 Tab 查看帧率"
        except OSError:
            info += "\n[警告] 文件不存在或路径无效"

        messagebox.showinfo("详细信息", info)

    def save_changes(self):
        if not self.config_path:
            messagebox.showerror("错误", "未加载配置文件")
            return
        if not messagebox.askyesno(
            "确认保存",
            f"将把 {len(self.entries)} 条记录写回配置文件，原文件将自动备份。\n是否继续？"
        ):
            return

        backup_path = self.config_path.with_suffix(
            f".ini.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        try:
            shutil.copy2(self.config_path, backup_path)
        except Exception as e:
            messagebox.showerror("错误", f"备份失败:\n{e}")
            return

        try:
            with open(self.config_path, 'r', encoding=self.file_encoding) as f:
                original_content = f.read()
            new_content = self.rebuild_config_content(original_content, self.entries)
            with open(self.config_path, 'w', encoding=self.file_encoding, newline='') as f:
                f.write(new_content)
            self.history = []
            self.update_button_states()
            self.status_var.set(
                f"保存成功！备份: {backup_path.name} | 共 {len(self.entries)} 条记录"
            )
            messagebox.showinfo("完成", f"保存成功！\n备份文件: {backup_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败:\n{e}")

    def rebuild_config_content(self, original_content, kept_entries):
        lines = original_content.splitlines()
        new_lines = []
        in_section = False
        section_found = False
        entry_index = 1

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[RememberFiles]'):
                in_section = True
                section_found = True
                new_lines.append(line)
                for _, frames, path in kept_entries:
                    new_lines.append(f"{entry_index}={frames}={path}")
                    entry_index += 1
                continue
            if in_section:
                if stripped.startswith('['):
                    in_section = False
                    new_lines.append(line)
                continue
            new_lines.append(line)

        if not section_found:
            new_lines.append('[RememberFiles]')
        return '\n'.join(new_lines)


if __name__ == '__main__':
    # 高分屏适配：告知 Windows 本程序 DPI 自适应，不需要系统拉伸
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        pass  # 非 Windows 环境静默跳过

    root = tk.Tk()
    app = RememberFilesManager(root)
    root.mainloop()

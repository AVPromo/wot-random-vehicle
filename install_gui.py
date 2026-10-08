#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_gui.py —— 图形界面一键安装 MOD
==========================================
tkinter GUI: 选择游戏目录 -> 自动探测版本 -> 安装 wotmod + 配置。
复用 install_wotmod.py / build_wotmod.py 的逻辑。

用法:
  python install_gui.py        # 或双击 install_gui.bat
"""

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from build_wotmod import CONFIG, WOTMOD, deploy, detect_version
from install_wotmod import DEFAULT_GAME_ROOT, find_game_root

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'install_gui_settings.json')

ICON_TEXT = 'WOT Random Vehicle MOD 安装器'


def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class InstallerGUI(object):

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(ICON_TEXT)
        self.root.minsize(640, 420)
        self.log_queue = queue.Queue()
        self.worker = None

        settings = load_settings()
        saved_root = settings.get('game_root')
        initial = find_game_root(saved_root) or saved_root or DEFAULT_GAME_ROOT

        self._build_widgets(initial)
        self.root.after(100, self._pump_log)
        self.root.after(200, self._validate_game_root)
        # 手动输入目录后, 回车或失焦时重新校验
        self.game_root_var.trace_add('write', self._on_game_root_changed)

    # ---------- UI ----------

    def _build_widgets(self, initial_root):
        pad = {'padx': 10, 'pady': 6}

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill='both', expand=True)

        # 游戏目录
        row1 = ttk.Frame(main)
        row1.pack(fill='x', **pad)
        ttk.Label(row1, text='游戏目录:').pack(side='left')
        self.game_root_var = tk.StringVar(value=initial_root)
        ttk.Entry(row1, textvariable=self.game_root_var).pack(
            side='left', fill='x', expand=True, padx=6)
        ttk.Button(row1, text='浏览...', command=self._browse_game_root).pack(
            side='left', padx=(0, 6))
        ttk.Button(row1, text='自动探测', command=self._auto_detect).pack(
            side='left')

        # 版本号(自动探测填充, 可手动修改覆盖)
        row2 = ttk.Frame(main)
        row2.pack(fill='x', **pad)
        ttk.Label(row2, text='客户端版本:').pack(side='left')
        self.version_var = tk.StringVar(value='')
        self.version_entry = ttk.Entry(row2, textvariable=self.version_var,
                                       width=16)
        self.version_entry.pack(side='left', padx=6)
        ttk.Label(row2, text='(自动从 paths.xml 探测, 可手动修改)',
                  foreground='#666').pack(side='left')

        # 状态行
        self.status_var = tk.StringVar(value='')
        ttk.Label(main, textvariable=self.status_var,
                  foreground='#0a7').pack(fill='x', **pad)

        # 日志区
        self.log_text = tk.Text(main, height=12, state='disabled',
                                font=('Consolas', 9), wrap='word')
        self.log_text.pack(fill='both', expand=True, **pad)

        # 按钮区
        row3 = ttk.Frame(main)
        row3.pack(fill='x', **pad)
        self.install_btn = ttk.Button(row3, text='安装',
                                      command=self._start_install)
        self.install_btn.pack(side='right')
        ttk.Button(row3, text='退出', command=self.root.destroy).pack(
            side='right', padx=(0, 10))

    # ---------- 辅助 ----------

    def log(self, msg):
        self.log_queue.put(msg)

    def _append_log(self, msg):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _pump_log(self):
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._pump_log)

    def _on_game_root_changed(self, *_):
        # 输入每个字符都会触发, 用 300ms 防抖后再校验
        if getattr(self, '_validate_job', None):
            self.root.after_cancel(self._validate_job)
        self._validate_job = self.root.after(300, self._validate_game_root)

    def _validate_game_root(self):
        self._validate_job = None
        root = self.game_root_var.get().strip()
        if root and os.path.exists(os.path.join(root, 'paths.xml')):
            self.status_var.set('目录有效: 找到 paths.xml')
            ver = detect_version(root)
            if ver:
                self.version_var.set(ver)
        else:
            self.status_var.set('未找到 paths.xml, 请确认目录是否为游戏根目录 '
                                '(或手动指定版本后继续)')

    def _browse_game_root(self):
        chosen = filedialog.askdirectory(
            initialdir=self.game_root_var.get() or '/',
            title='选择游戏根目录 (包含 paths.xml / WorldOfTanks.exe)')
        if chosen:
            self.game_root_var.set(os.path.normpath(chosen))

    def _auto_detect(self):
        found = find_game_root()
        if found:
            self.game_root_var.set(found)
            self.log('自动探测到游戏目录: %s' % found)
        else:
            messagebox.showwarning(
                '未找到游戏', '自动探测失败, 请点"浏览..."手动选择游戏目录。\n'
                '默认位置: %s' % DEFAULT_GAME_ROOT)

    # ---------- 安装 ----------

    def _start_install(self):
        if self.worker and self.worker.is_alive():
            return
        game_root = self.game_root_var.get().strip()
        if not game_root or not os.path.isdir(game_root):
            messagebox.showerror('目录无效', '请先设置有效的游戏目录。')
            return
        if not os.path.exists(WOTMOD):
            messagebox.showerror(
                '缺少构建产物',
                '找不到 %s\n\n请先运行 build_wotmod.py --deploy '
                '或 build_and_deploy.bat 生成。' % WOTMOD)
            return
        version = self.version_var.get().strip()
        if not version:
            version = detect_version(game_root)
            if not version:
                messagebox.showerror('版本未知', '无法探测客户端版本, 请手动填写。')
                return

        save_settings({'game_root': game_root})
        self.install_btn.configure(state='disabled')
        self.log('=' * 60)
        self.log('开始安装: 游戏目录=%s  版本=%s' % (game_root, version))
        self.worker = threading.Thread(
            target=self._do_install, args=(game_root, version), daemon=True)
        self.worker.start()

    def _do_install(self, game_root, version):
        try:
            deploy(game_root, version)
            self.log('')
            self.log('安装完成! 共 2 个文件:')
            self.log('  %s' % os.path.join(
                game_root, 'mods', version, 'mod_random_vehicle.wotmod'))
            self.log('  %s' % os.path.join(
                game_root, 'res_mods', version, 'gui', 'mods',
                'randomVehicle.xml'))
            self.log('重启游戏, 进入车库按 F11 随机选车。')
            self.root.after(0, lambda: self._on_done(True))
        except Exception as exc:  # noqa: BLE001
            self.log('[失败] %r' % (exc,))
            self.root.after(0, lambda: self._on_done(False))

    def _on_done(self, ok):
        self.install_btn.configure(state='normal')
        if ok:
            messagebox.showinfo('完成', '安装完成!\n重启游戏后按 F11 随机选车。')
        else:
            messagebox.showerror('失败', '安装失败, 详情见日志窗口。')


def main():
    app = InstallerGUI()
    app.root.mainloop()


if __name__ == '__main__':
    main()

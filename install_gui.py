#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_gui.py —— 图形界面一键安装 MOD
==========================================
tkinter GUI: 选择游戏目录 -> 自动探测版本 -> 安装 wotmod + 配置。
附带 MOD 配置编辑(按键/筛选), 保存后运行中的游戏约 1 秒内自动生效。
复用 install_wotmod.py / build_wotmod.py 的逻辑。

用法:
  python install_gui.py        # 或双击 install_gui.bat
"""

import json
import os
import queue
import shutil
import threading
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox, ttk

from build_wotmod import CONFIG, WOTMOD, deploy, detect_version
from install_wotmod import DEFAULT_GAME_ROOT, find_game_root

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'install_gui_settings.json')

ICON_TEXT = 'WOT Random Vehicle MOD 安装器'

# ---------------- MOD 配置选项 ----------------
KEY_CHOICES = ['KEY_F%d' % i for i in range(1, 13)] + [
    'KEY_G', 'KEY_H', 'KEY_J', 'KEY_K', 'KEY_L']
PREMIUM_MODES = ['不限', '只要金币车', '只要银币车']
CLASSES = [('lightTank', '轻坦'), ('mediumTank', '中坦'), ('heavyTank', '重坦'),
           ('AT-SPG', '坦克歼击车'), ('SPG', '自行火炮')]
NATIONS = [(0, '苏联'), (1, '德国'), (2, '美国'), (3, '法国'), (4, '英国'),
           (5, '中国'), (6, '日本'), (7, '捷克'), (8, '瑞典'), (9, '波兰'),
           (10, '意大利')]
TIERS = list(range(1, 11))

CONFIG_TEMPLATE = u'''<?xml version="1.0" encoding="UTF-8"?>
<root>
    <!-- 触发键: Keys 模块中的常量名, 例如 KEY_F10 / KEY_F11 / KEY_F12 -->
    <key>{key}</key>
    <!-- 按键轮询间隔(秒), 越小越灵敏, 0.10~0.20 为宜 -->
    <interval>{interval}</interval>

    <!-- ================= 筛选配置 ================= -->
    <!-- F11 随机选车时, 只从符合以下条件的车中随机。
         保存后运行中的游戏约 1 秒内自动生效, 无需重启。 -->
    <filters>
        <!-- 金币车: 0=不限  1=只要金币车  2=只要银币车 -->
        <premiumMode>{premium}</premiumMode>

        <!-- 坦克类型: lightTank 轻坦 / mediumTank 中坦 / heavyTank 重坦 /
             AT-SPG 坦克歼击车 / SPG 自行火炮
             多选用逗号分隔, 留空=全部
             例: <classes>heavyTank,mediumTank</classes> -->
        <classes>{classes}</classes>

        <!-- 国家(数字ID): 0=苏联 1=德国 2=美国 3=法国 4=英国 5=中国 6=日本
             7=捷克斯洛伐克 8=瑞典 9=波兰 10=意大利
             多选用逗号分隔, 留空=全部
             例: <nations>5,0</nations> -->
        <nations>{nations}</nations>

        <!-- 等级: 1 ~ 10, 多选用逗号分隔, 留空=全部
             例: <tiers>8,9,10</tiers> -->
        <tiers>{tiers}</tiers>
    </filters>
</root>
'''


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
        self.root.minsize(680, 640)
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

        # MOD 配置区
        self._build_config_widgets(main, pad)

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
        ttk.Button(row3, text='保存配置', command=self._on_save_config).pack(
            side='left')
        self.install_btn = ttk.Button(row3, text='安装',
                                      command=self._start_install)
        self.install_btn.pack(side='right')
        ttk.Button(row3, text='退出', command=self.root.destroy).pack(
            side='right', padx=(0, 10))

        self._load_config_into_ui()

    def _build_config_widgets(self, main, pad):
        cfg = ttk.LabelFrame(
            main, padding=8,
            text='MOD 配置 (保存后运行中的游戏约 1 秒内自动生效)')
        cfg.pack(fill='x', **pad)

        key_row = ttk.Frame(cfg)
        key_row.pack(fill='x', pady=2)
        ttk.Label(key_row, text='触发键:').pack(side='left')
        self.key_var = tk.StringVar(value='KEY_F11')
        ttk.Combobox(key_row, textvariable=self.key_var, values=KEY_CHOICES,
                     width=10).pack(side='left', padx=4)
        ttk.Label(key_row, text='轮询间隔:').pack(side='left', padx=(12, 0))
        self.interval_var = tk.StringVar(value='0.15')
        ttk.Entry(key_row, textvariable=self.interval_var,
                  width=6).pack(side='left', padx=4)
        ttk.Label(key_row, text='秒 (0.10~0.20 为宜)',
                  foreground='#666').pack(side='left')

        prem_row = ttk.Frame(cfg)
        prem_row.pack(fill='x', pady=2)
        ttk.Label(prem_row, text='金币车:').pack(side='left')
        self.premium_var = tk.StringVar(value=PREMIUM_MODES[0])
        ttk.Combobox(prem_row, textvariable=self.premium_var,
                     values=PREMIUM_MODES, width=10,
                     state='readonly').pack(side='left', padx=4)

        cls_row = ttk.Frame(cfg)
        cls_row.pack(fill='x', pady=2)
        ttk.Label(cls_row, text='坦克类型:').pack(side='left')
        self.class_vars = {}
        for tag, label in CLASSES:
            v = tk.IntVar()
            self.class_vars[tag] = v
            ttk.Checkbutton(cls_row, text=label, variable=v).pack(
                side='left', padx=4)
        ttk.Label(cls_row, text='不勾=全部', foreground='#666').pack(
            side='left', padx=6)

        nat_row = ttk.Frame(cfg)
        nat_row.pack(fill='x', pady=2)
        ttk.Label(nat_row, text='国家:').pack(side='left')
        nat_grid = ttk.Frame(nat_row)
        nat_grid.pack(side='left')
        self.nation_vars = {}
        for i, (nid, label) in enumerate(NATIONS):
            v = tk.IntVar()
            self.nation_vars[nid] = v
            ttk.Checkbutton(nat_grid, text=label, variable=v).grid(
                row=i // 6, column=i % 6, sticky='w', padx=4)
        ttk.Label(nat_row, text='不勾=全部', foreground='#666').pack(
            side='left', padx=6)

        tier_row = ttk.Frame(cfg)
        tier_row.pack(fill='x', pady=2)
        ttk.Label(tier_row, text='等级:').pack(side='left')
        self.tier_vars = {}
        for t in TIERS:
            v = tk.IntVar()
            self.tier_vars[t] = v
            ttk.Checkbutton(tier_row, text=str(t), variable=v).pack(
                side='left', padx=2)
        ttk.Label(tier_row, text='不勾=全部', foreground='#666').pack(
            side='left', padx=6)

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

    # ---------- MOD 配置 ----------

    @staticmethod
    def _split_set(text):
        return set(x.strip() for x in (text or '').split(',') if x.strip())

    def _load_config_into_ui(self):
        """把仓库里的 randomVehicle.xml 当前值填入界面。"""
        try:
            root = ET.parse(CONFIG).getroot()
        except Exception as exc:  # noqa: BLE001
            self.log('读取配置失败(使用默认值): %r' % (exc,))
            return
        key = (root.findtext('key') or '').strip()
        if key:
            self.key_var.set(key)
        interval = (root.findtext('interval') or '').strip()
        if interval:
            self.interval_var.set(interval)
        f = root.find('filters')
        if f is None:
            return
        try:
            pm = int((f.findtext('premiumMode') or '0').strip())
        except ValueError:
            pm = 0
        self.premium_var.set(PREMIUM_MODES[pm] if 0 <= pm < len(PREMIUM_MODES)
                             else PREMIUM_MODES[0])
        classes = self._split_set(f.findtext('classes'))
        for tag, var in self.class_vars.items():
            var.set(1 if tag in classes else 0)
        nations = self._split_set(f.findtext('nations'))
        for nid, var in self.nation_vars.items():
            var.set(1 if str(nid) in nations else 0)
        tiers = self._split_set(f.findtext('tiers'))
        for t, var in self.tier_vars.items():
            var.set(1 if str(t) in tiers else 0)

    def _save_config(self):
        """把界面值写回 randomVehicle.xml; 返回是否成功。"""
        key = self.key_var.get().strip() or 'KEY_F11'
        if not key.startswith('KEY_'):
            messagebox.showerror('按键无效',
                                 '触发键必须是 Keys 模块常量名(以 KEY_ 开头)。')
            return False
        try:
            interval = float(self.interval_var.get().strip())
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror('间隔无效', '轮询间隔必须是大于 0 的数字(秒)。')
            return False
        try:
            premium = PREMIUM_MODES.index(self.premium_var.get())
        except ValueError:
            premium = 0
        classes = ','.join(tag for tag, _ in CLASSES if self.class_vars[tag].get())
        nations = ','.join(str(n) for n, _ in NATIONS if self.nation_vars[n].get())
        tiers = ','.join(str(t) for t in TIERS if self.tier_vars[t].get())
        text = CONFIG_TEMPLATE.format(
            key=key, interval='%g' % interval, premium=premium,
            classes=classes, nations=nations, tiers=tiers)
        try:
            with open(CONFIG, 'w', encoding='utf-8') as fp:
                fp.write(text)
        except OSError as exc:
            messagebox.showerror('保存失败', '无法写入 %s\n%r' % (CONFIG, exc))
            return False
        self.log('配置已保存: %s' % CONFIG)

        # 同步到游戏 res_mods, 运行中的游戏会自动热读取
        game_root = self.game_root_var.get().strip()
        if game_root and os.path.exists(os.path.join(game_root, 'paths.xml')):
            version = self.version_var.get().strip() or detect_version(game_root)
            if version:
                target = os.path.join(game_root, 'res_mods', version,
                                      'gui', 'mods', 'randomVehicle.xml')
                try:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copyfile(CONFIG, target)
                    self.log('配置已同步到游戏: %s' % target)
                    self.log('运行中的游戏约 1 秒内自动读取, 无需重启。')
                except OSError as exc:
                    self.log('[警告] 同步配置到游戏失败: %r' % (exc,))
        else:
            self.log('游戏目录无效, 仅更新了仓库配置文件。')
        return True

    def _on_save_config(self):
        if self._save_config():
            messagebox.showinfo(
                '已保存',
                '配置已保存。\n若游戏正在运行, 约 1 秒内自动生效, 无需重启。')

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
        if not self._save_config():
            return
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

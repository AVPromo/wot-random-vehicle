#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_wotmod.py —— 一键安装 MOD 到游戏
==========================================
把已构建好的 dist/mod_random_vehicle.wotmod 和配置安装到游戏对应版本目录。
不需要重新编译(安装 dist 里的成品)。

用法:
  python install_wotmod.py                             # 自动定位游戏并安装
  python install_wotmod.py --game-root "C:/Games/World_of_Tanks_CN"   # 指定游戏目录
  python install_wotmod.py --version 2.3.1.1           # 指定版本(默认从 paths.xml 探测)

也可以直接双击 install_wotmod.bat。
"""

import argparse
import os
import sys

from build_wotmod import CONFIG, WOTMOD, deploy, detect_version

DEFAULT_GAME_ROOT = r'C:\Games\World_of_Tanks_CN'


def find_game_root(explicit=None):
    """定位游戏根目录(含 paths.xml 或 WorldOfTanks.exe 的目录)。"""
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get('WOT_GAME_ROOT')
    if env:
        candidates.append(env)
    # 若仓库被放进游戏目录内, 向上逐级找
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(cur, 'paths.xml')) or os.path.exists(os.path.join(cur, 'WorldOfTanks.exe')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    candidates.append(DEFAULT_GAME_ROOT)
    for c in candidates:
        if os.path.exists(os.path.join(c, 'paths.xml')):
            return c
    return None


def main():
    ap = argparse.ArgumentParser(description='一键安装 randomVehicle MOD')
    ap.add_argument('--game-root', default=None, help='游戏根目录(默认自动探测)')
    ap.add_argument('--version', default=None, help='客户端版本号(默认从 paths.xml 探测)')
    args = ap.parse_args()

    root = find_game_root(args.game_root)
    if not root:
        print('[错误] 找不到游戏目录。请用参数指定, 例如:')
        print('  python install_wotmod.py --game-root "C:/Games/World_of_Tanks_CN"')
        return 1
    print('游戏目录: %s' % root)

    if not os.path.exists(WOTMOD):
        print('[错误] 缺少构建产物 %s' % WOTMOD)
        print('       请先运行 build_wotmod.py 生成, 或运行 build_and_deploy.bat')
        return 1
    if not os.path.exists(CONFIG):
        print('[警告] 缺少配置 %s, 将使用默认 F11' % CONFIG)

    version = args.version or detect_version(root)
    print('客户端版本: %s' % version)

    deploy(root, version)
    print('')
    print('安装完成! 共 2 个文件:')
    print('  %s' % os.path.join(root, 'mods', version, 'mod_random_vehicle.wotmod'))
    print('  %s' % os.path.join(root, 'res_mods', version, 'gui', 'mods', 'randomVehicle.xml'))
    print('')
    print('重启游戏, 进入车库, 按 F11 随机选车。')
    print('改键: 编辑 randomVehicle.xml 里的 <key> 标签, 例如 KEY_F10 / KEY_F12。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

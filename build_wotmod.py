#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_wotmod.py —— 构建并(可选)部署 randomVehicle MOD
========================================================
步骤:
  1. 用 Python 2.7 把 src/mod_random_vehicle.py 编译为 .pyc (匹配游戏字节码魔数)
  2. 打包成"不压缩"zip 的 wotmod(根目录带 res/ 挂载根)
  3. (可选)部署到 <游戏根>/mods/<版本号>/ 和 res_mods/<版本号>/gui/mods/

用法:
  python build_wotmod.py                 # 仅构建 dist/mod_random_vehicle.wotmod
  python build_wotmod.py --deploy        # 构建并部署到游戏
  python build_wotmod.py --deploy --version 2.3.1.1 --game-root "C:/Games/World_of_Tanks_CN"

依赖: 系统需安装 Python 2.7 (默认 C:/Python27/python.exe)。
"""

import argparse
import os
import re
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src', 'mod_random_vehicle.py')
PYC = os.path.join(ROOT, 'build', 'mod_random_vehicle.pyc')
WOTMOD = os.path.join(ROOT, 'dist', 'mod_random_vehicle.wotmod')
CONFIG = os.path.join(ROOT, 'res', 'gui', 'mods', 'randomVehicle.xml')

META_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<root>\n'
    '  <id>mod_random_vehicle</id>\n'
    '  <name>Random Vehicle</name>\n'
    '  <version>1.0.7</version>\n'
    '  <description>Press F11 to select a random vehicle</description>\n'
    '</root>\n'
)


def compile_pyc(py27):
    """用 Python 2.7 编译源码为 .pyc(与游戏字节码魔数一致)。"""
    os.makedirs(os.path.dirname(PYC), exist_ok=True)
    src = SRC.replace('\\', '/')
    pyc = PYC.replace('\\', '/')
    script = "import py_compile; py_compile.compile('%s', '%s')" % (src, pyc)
    subprocess.check_call([py27, '-c', script])
    with open(PYC, 'rb') as f:
        magic = f.read(4)
    print('compiled -> %s (magic=%s)' % (PYC, magic.hex(' ')))
    assert magic == b'\x03\xf3\x0d\x0a', '魔数不是标准 Python 2.7, 换一个 2.7 构建重试'


def build_wotmod():
    """打包为不压缩 zip, 根目录带 res/ 挂载根。"""
    os.makedirs(os.path.dirname(WOTMOD), exist_ok=True)
    if os.path.exists(WOTMOD):
        os.remove(WOTMOD)
    with zipfile.ZipFile(WOTMOD, 'w', zipfile.ZIP_STORED) as z:
        z.write(PYC, 'res/scripts/client/gui/mods/mod_random_vehicle.pyc')
        z.writestr('meta.xml', META_XML)
    with zipfile.ZipFile(WOTMOD) as z:
        print('wotmod ->', WOTMOD)
        for i in z.infolist():
            print('   %-70s comp=%d' % (i.filename, i.compress_type))


def detect_version(game_root):
    """从 paths.xml 读取当前版本号。"""
    paths = os.path.join(game_root, 'paths.xml')
    try:
        with open(paths, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        m = re.search(r'res_mods/(\d+\.\d+\.\d+\.\d+)', text)
        if m:
            return m.group(1)
    except OSError:
        pass
    return '2.3.1.1'


def deploy(game_root, version):
    """部署到游戏目录。"""
    mods_dir = os.path.join(game_root, 'mods', version)
    os.makedirs(mods_dir, exist_ok=True)
    shutil.copy(WOTMOD, os.path.join(mods_dir, 'mod_random_vehicle.wotmod'))
    print('deployed ->', os.path.join(mods_dir, 'mod_random_vehicle.wotmod'))

    res_dir = os.path.join(game_root, 'res_mods', version, 'gui', 'mods')
    os.makedirs(res_dir, exist_ok=True)
    shutil.copy(CONFIG, os.path.join(res_dir, 'randomVehicle.xml'))
    print('deployed ->', os.path.join(res_dir, 'randomVehicle.xml'))


def main():
    ap = argparse.ArgumentParser(description='Build randomVehicle MOD')
    ap.add_argument('--py27', default=r'C:\Python27\python.exe', help='Python 2.7 路径')
    ap.add_argument('--game-root', default=r'C:\Games\World_of_Tanks_CN')
    ap.add_argument('--version', default=None, help='版本号, 默认从 paths.xml 探测')
    ap.add_argument('--deploy', action='store_true', help='构建后部署到游戏')
    args = ap.parse_args()

    compile_pyc(args.py27)
    build_wotmod()
    if args.deploy:
        version = args.version or detect_version(args.game_root)
        deploy(args.game_root, version)
    print('done.')


if __name__ == '__main__':
    main()

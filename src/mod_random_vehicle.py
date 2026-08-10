# -*- coding: utf-8 -*-
"""
mod_random_vehicle.py —— 车库随机选车 GUI MOD (WOT CN 2.3.x)
================================================================
按 F11(可在 res/gui/mods/randomVehicle.xml 改键)在车库随机选中自己的一辆战车。

运行环境: 客户端内置 Python 2.7 + BigWorld
数据范围: 仅使用客户端已有数据(自己已拥有的战车), 等同于替玩家点击车辆,
          不读取服务器未下发信息, 不含任何作弊逻辑。

2.3.1.1 客户端的关键 API(均已通过游戏脚本包字节码核实):
  * 车辆列表: itemsCache.items.getVehicles() 然后过滤 isInInventory (只留已拥有)
  * 选车:     gui.shared.event_dispatcher.selectVehicleInHangar(intCD)
              (官方 API: 派发 SELECT_VEHICLE_IN_HANGAR 事件 + selectVehicle + showHangar)
  * 按键:     BigWorld.isKeyDown(Keys.KEY_F11)

部署(见 README):
  * 编译为 .pyc (Python 2.7), 打包进 wotmod: res/scripts/client/gui/mods/mod_random_vehicle.pyc
  * wotmod 必须是"不压缩"zip, 根目录带 res/ 挂载根
  * 放到 <游戏根>/mods/<版本号>/mod_random_vehicle.wotmod
"""

import os
import random
import time

import BigWorld

# ---------------------------------------------------------------------------
# 诊断与日志(写 .debug 文件到游戏根目录, 便于排障)
# ---------------------------------------------------------------------------
def _trace(msg):
    try:
        p = os.path.join(os.getcwd(), 'mod_random_vehicle.debug')
        with open(p, 'a') as f:
            f.write('%s | %s | %s\n' % (time.strftime('%H:%M:%S'), msg, __file__))
    except Exception:
        pass


def _log(msg):
    try:
        from debug_utils import LOG_DEBUG
        LOG_DEBUG('[mod_random_vehicle] ' + msg)
    except Exception:
        pass
    _trace('LOG: ' + msg)


# ---------------------------------------------------------------------------
# 配置(可被 res/gui/mods/randomVehicle.xml 覆盖)
# ---------------------------------------------------------------------------
KEY_NAME = 'KEY_F11'
POLL_INTERVAL = 0.15
SELECT_COOLDOWN = 0.4
FALLBACK_KEY = 0x57          # KEY_F11 的 DIK 扫描码备用值


def _load_config():
    global KEY_NAME, POLL_INTERVAL
    try:
        from ResMgr import openSection
        sec = openSection('gui/mods/randomVehicle.xml')
        if sec is not None:
            k = sec.readString('key')
            if k:
                KEY_NAME = k
            iv = sec.readFloat('interval')
            if iv and iv > 0:
                POLL_INTERVAL = iv
        _trace('config loaded, key=%s' % KEY_NAME)
    except Exception as e:
        _trace('config error: %r' % (e,))


def _key_code():
    try:
        import Keys
        return getattr(Keys, KEY_NAME, FALLBACK_KEY)
    except Exception as e:
        _trace('key_code fallback: %r' % (e,))
        return FALLBACK_KEY


# ---------------------------------------------------------------------------
# 运行时状态
# ---------------------------------------------------------------------------
_POLL_ON = [False]
_WAS_DOWN = [False]
_LAST_TIME = [0.0]


# ---------------------------------------------------------------------------
# 车辆列表 / 选车
# ---------------------------------------------------------------------------
def _get_owned_cds():
    """返回自己已拥有的战车 intCD 列表。"""
    cds = []
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        itemsCache = dependency.instance(IItemsCache)
        v = itemsCache.items.getVehicles()
        if isinstance(v, dict):
            cds = [cd for cd, veh in v.iteritems() if getattr(veh, 'isInInventory', False)]
        else:
            cds = [getattr(x, 'intCD', None) for x in v if getattr(x, 'isInInventory', False)]
        cds = [c for c in cds if c]
        _trace('owned vehicles count=%d' % len(cds))
    except Exception as e:
        _trace('getVehicles error: %r' % (e,))
    return cds


def _select_vehicle(cd):
    # 1) 官方"在车库选中车辆"API(反汇编确认: 事件+selectVehicle+showHangar)
    try:
        from gui.shared.event_dispatcher import selectVehicleInHangar
        selectVehicleInHangar(cd)
        _trace('select: selectVehicleInHangar(%s) called' % cd)
        return True
    except Exception as e:
        _trace('select: selectVehicleInHangar error: %r' % (e,))
    # 2) 兜底
    try:
        from CurrentVehicle import g_currentVehicle
        if g_currentVehicle.isPresent():
            g_currentVehicle.selectVehicle(cd)
            _trace('select: fallback g_currentVehicle.selectVehicle(%s)' % cd)
            return True
    except Exception as e:
        _trace('select: fallback error: %r' % (e,))
    return False


def _in_battle():
    try:
        p = BigWorld.player()
        if p is None:
            return False
        return 'Avatar' in p.__class__.__name__
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 按键处理
# ---------------------------------------------------------------------------
def _on_hotkey():
    _trace('HOTKEY triggered')
    if _in_battle():
        _trace('HOTKEY: in battle, skip')
        return
    now = time.time()
    if now - _LAST_TIME[0] < SELECT_COOLDOWN:
        _trace('HOTKEY: cooldown, skip')
        return
    _LAST_TIME[0] = now
    cds = _get_owned_cds()
    if not cds:
        _trace('HOTKEY: no vehicles available')
        return
    cur = None
    try:
        from CurrentVehicle import g_currentVehicle
        if g_currentVehicle.isPresent():
            cur = g_currentVehicle.item.intCD
    except Exception as e:
        _trace('HOTKEY: current vehicle error: %r' % (e,))
    pool = [c for c in cds if c != cur] or cds
    target = random.choice(pool)
    _trace('HOTKEY: pool=%d cur=%s target=%s' % (len(pool), cur, target))
    ok = _select_vehicle(target)
    _trace('HOTKEY: select result=%s' % ok)


def _tick():
    if not _POLL_ON[0]:
        return
    down = False
    try:
        down = bool(BigWorld.isKeyDown(_key_code()))
    except Exception:
        down = False
    if down and not _WAS_DOWN[0]:
        _on_hotkey()          # 上升沿触发, 按住不重复
    _WAS_DOWN[0] = down
    try:
        BigWorld.callback(POLL_INTERVAL, _tick)
    except Exception:
        _POLL_ON[0] = False


def _start():
    if _POLL_ON[0]:
        return
    _POLL_ON[0] = True
    try:
        BigWorld.callback(POLL_INTERVAL, _tick)
        _trace('start: poll callback scheduled OK')
    except Exception as e:
        _POLL_ON[0] = False
        _trace('start: poll FAILED: %r' % (e,))


def _stop():
    _POLL_ON[0] = False
    _trace('stop: poll stopped')


# ---------------------------------------------------------------------------
# GUI MOD 标准接口(原生加载器会调用; 模块级也双保险启动)
# ---------------------------------------------------------------------------
def init():
    _trace('init() called')
    _start()


def fini():
    _stop()


def finit():
    _stop()


# 模块级双保险: 被 import 即启动
_trace('module loaded, starting')
_load_config()
_start()

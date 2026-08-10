# -*- coding: utf-8 -*-
"""
mod_random_vehicle.py —— 车库随机选车 GUI MOD (WOT CN 2.3.x)
================================================================
* 按 F11 随机选中自己的一辆战车(可改键)
* 筛选配置写在 res/gui/mods/randomVehicle.xml 的 <filters> 节点
  (金币车 / 坦克类型 / 国家 / 等级, 逗号分隔多选, 留空=全部)
* 纯客户端功能, 不读取服务器未下发信息, 不含任何作弊逻辑

2.3.1.1 关键 API(经游戏字节码核实):
  * 车辆列表: itemsCache.items.getVehicles() -> 过滤 isInInventory
  * 选车:     gui.shared.event_dispatcher.selectVehicleInHangar(intCD)
  * 按键:     BigWorld.isKeyDown(Keys.KEY_F11)
"""

import os
import random
import time

import BigWorld

# ---------------------------------------------------------------------------
# 诊断与日志
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
# 配置
# ---------------------------------------------------------------------------
KEY_NAME = 'KEY_F11'
POLL_INTERVAL = 0.15
SELECT_COOLDOWN = 0.4
FALLBACK_KEY = 0x57

# 筛选状态: premiumMode 0=不限 1=只要金币 2=只要银币
_FILTERS = {'premiumMode': 0, 'classes': set(), 'nations': set(), 'tiers': set()}


def _read_set(ds, key, conv=None):
    """从配置节点读取逗号分隔的多选集合; 留空=全部。"""
    s = ds.readString(key)
    if s:
        vals = [x.strip() for x in s.split(',') if x.strip()]
        if conv:
            vals = [conv(v) for v in vals]
        _FILTERS[key] = set(vals)
    else:
        _FILTERS[key] = set()


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
            f = sec['filters']
            if f is not None:
                _FILTERS['premiumMode'] = f.readInt('premiumMode', 0)
                _read_set(f, 'classes')
                _read_set(f, 'nations', int)
                _read_set(f, 'tiers', int)
                _trace('config loaded, key=%s, filters=%s' % (KEY_NAME, _FILTERS))
            else:
                _trace('config loaded, key=%s (no filters)' % KEY_NAME)
    except Exception as e:
        _trace('config error: %r' % (e,))


def _key_code():
    try:
        import Keys
        return getattr(Keys, KEY_NAME, FALLBACK_KEY)
    except Exception:
        return FALLBACK_KEY


# ---------------------------------------------------------------------------
# 运行时状态
# ---------------------------------------------------------------------------
_POLL_ON = [False]
_WAS_DOWN = [False]
_LAST_TIME = [0.0]


# ---------------------------------------------------------------------------
# 筛选
# ---------------------------------------------------------------------------
# 仅限特定模式的活动/租用车辆标志(存在库存数据但不算自己的车库车)
_MODE_ONLY_FLAGS = (
    'isOnlyForBattleRoyaleBattles', 'isOnlyForEpicBattles',
    'isOnlyForEventBattles', 'isOnlyForClanWarsBattles',
    'isOnlyForComp7Battles', 'isOnlyForMapsTrainingBattles',
)


def _is_usable_garage_vehicle(veh):
    """判断是否是自己车库真正可用的车(排除模式活动租用车)。"""
    if not getattr(veh, 'isInInventory', False):
        return False
    for flag in _MODE_ONLY_FLAGS:
        try:
            if getattr(veh, flag, False):
                return False
        except Exception:
            pass
    return True


def _apply_filters(vehicles):
    """按配置筛选已拥有车辆, 返回 intCD 列表(空集合=全部)。"""
    out = []
    f = _FILTERS
    for cd, veh in vehicles.iteritems():
        if not _is_usable_garage_vehicle(veh):
            continue
        if f['premiumMode'] == 1 and not getattr(veh, 'isPremium', False):
            continue
        if f['premiumMode'] == 2 and getattr(veh, 'isPremium', False):
            continue
        t = _veh_class(veh)
        if f['classes'] and t not in f['classes']:
            continue
        nid = getattr(veh, 'nationID', None)
        if f['nations'] and nid not in f['nations']:
            continue
        lv = getattr(veh, 'level', None)
        if f['tiers'] and lv not in f['tiers']:
            continue
        out.append(cd)
    return out


# ---------------------------------------------------------------------------
# 车辆列表 / 选车
# ---------------------------------------------------------------------------
def _select_vehicle(cd):
    try:
        from gui.shared.event_dispatcher import selectVehicleInHangar
        selectVehicleInHangar(cd)
        _trace('select: selectVehicleInHangar(%s) called' % cd)
        return True
    except Exception as e:
        _trace('select: selectVehicleInHangar error: %r' % (e,))
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
def _veh_class(veh):
    """获取车辆类型, 多路径尝试。"""
    try:
        vt = veh.type
    except Exception:
        vt = None
    if vt is not None:
        for attr in ('typeName', 'classTag'):
            try:
                t = getattr(vt, attr, None)
                if t:
                    return t
            except Exception:
                continue
        try:
            tags = vt.tags
            for c in ('lightTank', 'mediumTank', 'heavyTank', 'AT-SPG', 'SPG'):
                if c in tags:
                    return c
        except Exception:
            pass
    # 直接看 veh.tags
    try:
        tags = veh.tags
        for c in ('lightTank', 'mediumTank', 'heavyTank', 'AT-SPG', 'SPG'):
            if c in tags:
                return c
    except Exception:
        pass
    return '?'


def _dump_owned_stats(owned):
    classes = {}
    prem = 0
    for _cd, veh in owned.iteritems():
        t = _veh_class(veh)
        classes[t] = classes.get(t, 0) + 1
        if getattr(veh, 'isPremium', False):
            prem += 1
    _trace('DIAG: 类型分布 %s | 金币=%d 银币=%d' % (classes, prem, len(owned) - prem))


def _veh_state_flags(veh):
    """输出车辆状态标志, 用于区分"幽灵车"。"""
    parts = []
    for attr in ('isRented', 'rentalIsOver', 'isLocked', 'isDisabled',
                 'isPurchased', 'isCollectible', 'isInBattle', 'isRestoreAvailable',
                 'isOnlyForBattleRoyaleBattles', 'isOnlyForEpicBattles',
                 'isOnlyForEventBattles', 'isOnlyForClanWarsBattles',
                 'isOnlyForComp7Battles', 'isOnlyForMapsTrainingBattles',
                 'isEvent', 'isEpicActionVehicle', 'isWotPlus', 'isTelecom'):
        try:
            if getattr(veh, attr, False):
                parts.append(attr)
        except Exception:
            pass
    try:
        st = veh.getState()
        parts.append('state=%s' % st)
    except Exception as e:
        parts.append('stateErr=%s' % repr(e)[:40])
    return ','.join(parts)


def _dump_vehicle_list(owned):
    """列出全部已拥有车辆, 便于人工核对。"""
    for cd, veh in sorted(owned.iteritems()):
        try:
            name = veh.userName
        except Exception:
            name = '?'
        c = _veh_class(veh)
        prem = u'金' if getattr(veh, 'isPremium', False) else u'银'
        nid = getattr(veh, 'nationID', '?')
        lv = getattr(veh, 'level', '?')
        _trace(u'DIAG VEH: cd=%s | %s | %s | %s | 国%s L%s | %s' %
               (cd, name, c, prem, nid, lv, _veh_state_flags(veh)))


def _get_owned_vehicles():
    """用 REQ_CRITERIA.INVENTORY 取自己已拥有的车(游戏权威过滤)。"""
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        from gui.shared.utils.requesters import REQ_CRITERIA
        owned = dependency.instance(IItemsCache).items.getVehicles(REQ_CRITERIA.INVENTORY)
        owned = dict((cd, veh) for cd, veh in owned.iteritems() if _is_usable_garage_vehicle(veh))
        return owned
    except Exception as e:
        _trace('DIAG: getVehicles(INVENTORY) error: %r' % (e,))
    # 兜底: 全量 + isInInventory 过滤
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        v = dependency.instance(IItemsCache).items.getVehicles()
        owned = dict((cd, veh) for cd, veh in v.iteritems() if _is_usable_garage_vehicle(veh))
        return owned
    except Exception as e:
        _trace('DIAG: getVehicles fallback error: %r' % (e,))
    return None


def _on_hotkey():
    if _in_battle():
        _trace('HOTKEY: in battle, skip')
        return
    now = time.time()
    if now - _LAST_TIME[0] < SELECT_COOLDOWN:
        _trace('HOTKEY: cooldown, skip')
        return
    _LAST_TIME[0] = now
    vehicles = _get_owned_vehicles()
    if not vehicles:
        _trace('HOTKEY: vehicles error')
        return
    cds = _apply_filters(vehicles)
    _trace('HOTKEY: filtered pool=%d (premium=%d classes=%s nations=%s tiers=%s)' %
           (len(cds), _FILTERS['premiumMode'], sorted(_FILTERS['classes']),
            sorted(_FILTERS['nations']), sorted(_FILTERS['tiers'])))
    if not cds:
        _trace('HOTKEY: no vehicles match filters')
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
    _trace('HOTKEY: target=%s' % target)
    _select_vehicle(target)


def _tick():
    if not _POLL_ON[0]:
        return
    down = False
    try:
        down = bool(BigWorld.isKeyDown(_key_code()))
    except Exception:
        down = False
    if down and not _WAS_DOWN[0]:
        _on_hotkey()
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
# GUI MOD 标准接口
# ---------------------------------------------------------------------------
def init():
    _trace('init() called')
    _start()


def fini():
    _stop()


def finit():
    _stop()


def _delayed_dump():
    """启动延迟几秒后输出车库统计(等 items cache 同步), 供排障参考。"""
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        from gui.shared.utils.requesters import REQ_CRITERIA
        owned = dependency.instance(IItemsCache).items.getVehicles(REQ_CRITERIA.INVENTORY)
        owned = dict((cd, veh) for cd, veh in owned.iteritems() if _is_usable_garage_vehicle(veh))
        _trace('DIAG: 车库可用车辆 %d 辆' % len(owned))
        _dump_owned_stats(owned)
        _dump_vehicle_list(owned)
    except Exception as e:
        _trace('DIAG: delayed dump error: %r' % (e,))


# 模块级双保险
_trace('module loaded, starting')
_load_config()
_start()
BigWorld.callback(8.0, _delayed_dump)

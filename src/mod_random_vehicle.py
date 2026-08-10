# -*- coding: utf-8 -*-
"""
mod_random_vehicle.py —— 车库随机选车 GUI MOD (WOT CN 2.3.x)
================================================================
* 按 F11 随机选中自己的一辆战车(可改键)
* 车库右上角常驻设置面板: 筛选随机池(金币车/坦克类型/国家/等级)
* 纯客户端功能, 不读取服务器未下发信息, 不含任何作弊逻辑

2.3.1.1 关键 API(经游戏字节码核实):
  * 车辆列表: itemsCache.items.getVehicles() -> 过滤 isInInventory
  * 选车:     gui.shared.event_dispatcher.selectVehicleInHangar(intCD)
  * 按键:     BigWorld.isKeyDown(Keys.KEY_F11)
  * 面板:     BigWorld GUI 模块(GUI.Simple/GUI.Text) + gui.g_mouseEventHandlers
"""

import os
import random
import time

import BigWorld

try:
    import GUI
    _GUI_OK = True
except Exception:
    GUI = None
    _GUI_OK = False

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
_SAVE_PATH = 'mods/configs/mod_random_vehicle/filters.xml'

# 面板布局
PANEL_W = 240
MARGIN_R = 8
MARGIN_T = 8
BTN_H = 22
GAP = 2

_CLASS_KEYS = (
    ('lightTank', u'轻'), ('mediumTank', u'中'), ('heavyTank', u'重'),
    ('AT-SPG', u'歼'), ('SPG', u'炮'),
)
_NATION_NAMES = {
    0: u'苏', 1: u'德', 2: u'美', 3: u'法', 4: u'英', 5: u'中', 6: u'日',
    7: u'捷', 8: u'瑞', 9: u'波', 10: u'意',
}


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
    except Exception:
        return FALLBACK_KEY


# ---------------------------------------------------------------------------
# 运行时状态
# ---------------------------------------------------------------------------
_POLL_ON = [False]
_WAS_DOWN = [False]
_LAST_TIME = [0.0]
_PANEL = {'built': False, 'visible': False}
_COMPONENTS = []
_BUTTONS = []
_AVAIL_NATIONS = []
_AVAIL_TIERS = []
_HANGAR_ACTIVE = [False]
_HANGAR_PATCHED = [False]
_CURSOR_STAT = [0, 1e9, -1e9, 1e9, -1e9, 0]   # count,minx,maxx,miny,maxy,conv
_CLICK_LOCK = set()


# ---------------------------------------------------------------------------
# GUI 构造辅助
# ---------------------------------------------------------------------------
def _np(px, py):
    """像素坐标 -> 归一化坐标(中心锚点, 满屏宽=2)。"""
    sr = GUI.screenResolution()
    nx = 2.0 * px / sr[0] - 1.0
    ny = 1.0 - 2.0 * py / sr[1]
    return (nx, ny, 0)


def _get_tex():
    for t in ('gui/textures/mods/mod_random_vehicle/button.png',
              'mods/configs/mod_random_vehicle/button.png',
              '../../mods/configs/mod_random_vehicle/button.png'):
        try:
            GUI.Simple(t)
            return t
        except Exception:
            continue
    return None


def _panel_color(active):
    return (255, 210, 0, 255) if active else (60, 60, 60, 220)


def _make_button(x, y, w, h, active):
    t = _get_tex()
    if t is None:
        raise RuntimeError('no button texture')
    b = GUI.Simple(t)
    b.widthMode = b.heightMode = GUI.Simple.eSizeMode.PIXEL
    b.verticalPositionMode = b.horizontalPositionMode = GUI.Simple.ePositionMode.CLIP
    b.width, b.height = w, h
    b.horizontalAnchor, b.verticalAnchor = GUI.Simple.eHAnchor.CENTER, GUI.Simple.eVAnchor.CENTER
    b.position = _np(x + w / 2.0, y + h / 2.0)
    b.materialFX, b.filterType = GUI.Simple.eMaterialFX.BLEND, GUI.Simple.eFilterType.LINEAR
    b.colour = _panel_color(active)
    _COMPONENTS.append(b)
    return b


def _make_text(text):
    c = None
    try:
        c = GUI.Text(text)
    except Exception:
        try:
            c = GUI.TextComponent(text)
        except Exception:
            c = None
    if c is None:
        return None
    for f in ('system_small.font', 'default_smaller.font'):
        try:
            c.font = f
            break
        except Exception:
            continue
    try:
        c.colour = (255, 255, 255, 255)
    except Exception:
        pass
    return c


def _add_text(x, y, w, h, s):
    c = _make_text(s)
    if c is None:
        return None
    try:
        c.horizontalAnchor = GUI.Simple.eHAnchor.CENTER
        c.verticalAnchor = GUI.Simple.eVAnchor.CENTER
    except Exception:
        pass
    c.position = _np(x + w / 2.0, y + h / 2.0)
    _COMPONENTS.append(c)
    return c


# ---------------------------------------------------------------------------
# 面板构建与生命周期
# ---------------------------------------------------------------------------
def _premium_label():
    return {0: u'不限', 1: u'只要金币', 2: u'只要银币'}.get(_FILTERS['premiumMode'], u'不限')


def _cycle_premium():
    _FILTERS['premiumMode'] = (_FILTERS['premiumMode'] + 1) % 3


def _toggle_set(key, val):
    s = _FILTERS[key]
    if val in s:
        s.discard(val)
    else:
        s.add(val)


def _redraw_buttons():
    for b in _BUTTONS:
        try:
            b['comp'].colour = _panel_color(b['active']())
        except Exception:
            pass


def _build_components():
    global _BUTTONS
    _BUTTONS = []
    _refresh_pool_meta()
    if not _GUI_OK:
        return
    sr = GUI.screenResolution()
    ox = sr[0] - MARGIN_R - PANEL_W
    oy = MARGIN_T
    ly = 0

    _add_text(ox + 4, oy + ly, PANEL_W - 8, 18, u'随机选车过滤')
    ly += 20

    # 金币车
    _add_text(ox + 4, oy + ly, 56, BTN_H, u'金币车')
    b = _make_button(ox + 64, oy + ly, 172, BTN_H, _FILTERS['premiumMode'] != 0)
    _BUTTONS.append({'rect': (ox + 64, oy + ly, 172, BTN_H), 'key': 'premium',
                     'comp': b, 'active': lambda: _FILTERS['premiumMode'] != 0,
                     'toggle': _cycle_premium})
    _add_text(ox + 150, oy + ly, 80, BTN_H, _premium_label())
    ly += BTN_H + GAP

    # 类型
    _add_text(ox + 4, oy + ly, 56, BTN_H, u'类型')
    bx = ox + 64
    for cname, clabel in _CLASS_KEYS:
        b = _make_button(bx, oy + ly, 44, BTN_H, cname in _FILTERS['classes'])
        _BUTTONS.append({'rect': (bx, oy + ly, 44, BTN_H), 'key': ('class', cname),
                         'comp': b, 'active': lambda c=cname: c in _FILTERS['classes'],
                         'toggle': (lambda c=cname: _toggle_set('classes', c))})
        _add_text(bx, oy + ly, 44, BTN_H, clabel)
        bx += 46
    ly += BTN_H + GAP

    # 国家(每行6个)
    if _AVAIL_NATIONS:
        _add_text(ox + 4, oy + ly, 56, BTN_H, u'国家')
        row, bx = 0, ox + 64
        for nid in _AVAIL_NATIONS:
            if row == 6:
                row, bx = 0, ox + 64
                ly += BTN_H + GAP
            b = _make_button(bx, oy + ly, 36, BTN_H, nid in _FILTERS['nations'])
            _BUTTONS.append({'rect': (bx, oy + ly, 36, BTN_H), 'key': ('nation', nid),
                             'comp': b, 'active': lambda n=nid: n in _FILTERS['nations'],
                             'toggle': (lambda n=nid: _toggle_set('nations', n))})
            _add_text(bx, oy + ly, 36, BTN_H, _NATION_NAMES.get(nid, str(nid)))
            bx += 38
            row += 1
        ly += BTN_H + GAP

    # 等级(每行5个)
    if _AVAIL_TIERS:
        _add_text(ox + 4, oy + ly, 56, BTN_H, u'等级')
        row, bx = 0, ox + 64
        for tier in _AVAIL_TIERS:
            if row == 5:
                row, bx = 0, ox + 64
                ly += BTN_H + GAP
            b = _make_button(bx, oy + ly, 44, BTN_H, tier in _FILTERS['tiers'])
            _BUTTONS.append({'rect': (bx, oy + ly, 44, BTN_H), 'key': ('tier', tier),
                             'comp': b, 'active': lambda t=tier: t in _FILTERS['tiers'],
                             'toggle': (lambda t=tier: _toggle_set('tiers', t))})
            _add_text(bx, oy + ly, 44, BTN_H, str(tier))
            bx += 46
            row += 1
        ly += BTN_H + GAP


def _init_panel():
    try:
        _build_components()
        for c in _COMPONENTS:
            GUI.addRoot(c)
        _PANEL['built'] = True
        _trace('panel built: %d components, nations=%s tiers=%s' %
               (len(_COMPONENTS), _AVAIL_NATIONS, _AVAIL_TIERS))
    except Exception as e:
        _PANEL['built'] = False
        _trace('panel build error: %r' % (e,))


def _rebuild_panel():
    global _COMPONENTS, _BUTTONS
    for c in _COMPONENTS:
        try:
            GUI.delRoot(c)
        except Exception:
            pass
    _COMPONENTS = []
    _BUTTONS = []
    _PANEL['built'] = False
    _PANEL['visible'] = False
    _trace('panel rebuilt')


def _show_panel():
    if not _PANEL.get('built'):
        _init_panel()
    if _PANEL.get('built'):
        for c in _COMPONENTS:
            try:
                c.visible = True
            except Exception:
                pass
        _PANEL['visible'] = True


def _hide_panel():
    if _PANEL.get('visible'):
        for c in _COMPONENTS:
            try:
                c.visible = False
            except Exception:
                pass
        _PANEL['visible'] = False


def _on_gui_reset():
    try:
        _rebuild_panel()
    except Exception as e:
        _trace('gui reset error: %r' % (e,))


# ---------------------------------------------------------------------------
# 可见性(仅车库显示)
# ---------------------------------------------------------------------------
def _in_garage():
    if _in_battle():
        return False
    try:
        p = BigWorld.player()
        if p is None:
            return False
        if 'Avatar' in p.__class__.__name__:
            return False
    except Exception:
        return False
    if _HANGAR_PATCHED[0]:
        return _HANGAR_ACTIVE[0]
    return True   # 未 patch 成功时降级: 非战斗即视为车库


def _ensure_hangar_patch():
    if _HANGAR_PATCHED[0]:
        return
    _HANGAR_PATCHED[0] = True
    try:
        from gui.Scaleform.daapi.view.lobby.hangar.Hangar import Hangar
        _op = Hangar._populate
        _od = Hangar._dispose

        def _pop(self, *a, **k):
            _HANGAR_ACTIVE[0] = True
            return _op(self, *a, **k)

        def _dis(self):
            _HANGAR_ACTIVE[0] = False
            return _od(self)

        Hangar._populate = _pop
        Hangar._dispose = _dis
        _trace('hangar patched')
    except Exception as e:
        _trace('hangar patch error: %r' % (e,))


def _update_panel_visibility():
    if _in_garage():
        if not _PANEL.get('visible'):
            _show_panel()
    else:
        if _PANEL.get('visible'):
            _hide_panel()


# ---------------------------------------------------------------------------
# 筛选
# ---------------------------------------------------------------------------
def _refresh_pool_meta():
    global _AVAIL_NATIONS, _AVAIL_TIERS
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        vehicles = dependency.instance(IItemsCache).items.getVehicles()
        ns, ts = set(), set()
        for _cd, veh in vehicles.iteritems():
            if not getattr(veh, 'isInInventory', False):
                continue
            n = getattr(veh, 'nationID', None)
            if n is not None:
                ns.add(n)
            lv = getattr(veh, 'level', None)
            if lv is not None:
                ts.add(lv)
        _AVAIL_NATIONS = sorted(ns)
        _AVAIL_TIERS = sorted(ts)
    except Exception as e:
        _trace('refresh meta error: %r' % (e,))


def _apply_filters(vehicles):
    """按筛选条件过滤已拥有车辆, 返回 intCD 列表(空集合=全部)。"""
    out = []
    f = _FILTERS
    for cd, veh in vehicles.iteritems():
        if not getattr(veh, 'isInInventory', False):
            continue
        if f['premiumMode'] == 1 and not getattr(veh, 'isPremium', False):
            continue
        if f['premiumMode'] == 2 and getattr(veh, 'isPremium', False):
            continue
        try:
            t = veh.type.typeName
        except Exception:
            t = None
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
# 持久化
# ---------------------------------------------------------------------------
def _read_filters_from(ds):
    try:
        _FILTERS['premiumMode'] = ds.readInt('premiumMode', 0)
        s = ds.readString('classes')
        if s:
            _FILTERS['classes'] = set(x for x in s.split(',') if x)
        for k in ('nations', 'tiers'):
            s = ds.readString(k)
            if s:
                _FILTERS[k] = set(int(x) for x in s.split(',') if x.strip())
    except Exception as e:
        _trace('read filters error: %r' % (e,))


def _save_filters():
    try:
        import ResMgr
        ds = ResMgr.openSection(_SAVE_PATH, 'write')
        if ds is None:
            ds = ResMgr.DataSection(_SAVE_PATH)
        ds.writeInt('premiumMode', _FILTERS['premiumMode'])
        ds.writeString('classes', ','.join(sorted(_FILTERS['classes'])))
        ds.writeString('nations', ','.join(str(n) for n in sorted(_FILTERS['nations'])))
        ds.writeString('tiers', ','.join(str(t) for t in sorted(_FILTERS['tiers'])))
        ds.save()
        _trace('filters saved')
    except Exception as e:
        _trace('save filters error: %r' % (e,))


def _load_filters():
    try:
        import ResMgr
        ds = ResMgr.openSection(_SAVE_PATH)
        if ds is not None:
            _read_filters_from(ds)
            _trace('filters loaded: %s' % (_FILTERS,))
            return
    except Exception:
        pass
    try:
        import ResMgr
        sec = ResMgr.openSection('gui/mods/randomVehicle.xml')
        if sec is not None:
            f = sec['filters']
            if f is not None:
                _read_filters_from(f)
                _trace('filters loaded from randomVehicle.xml')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 鼠标点击
# ---------------------------------------------------------------------------
def _event_to_px(event):
    try:
        cp = event.cursorPosition
        x, y = cp[0], cp[1]
    except Exception:
        return None
    s = _CURSOR_STAT
    if s[5] == 0:
        _probe_cursor(x, y)
    sr = GUI.screenResolution()
    if s[5] == 1:
        return ((x + 1.0) / 2.0 * sr[0], (1.0 - y) / 2.0 * sr[1])
    if s[5] == 2:
        return (x * sr[0], y * sr[1])
    return (x, y)


def _probe_cursor(x, y):
    s = _CURSOR_STAT
    s[0] += 1
    s[1], s[2] = min(s[1], x), max(s[2], x)
    s[3], s[4] = min(s[3], y), max(s[4], y)
    if s[0] >= 25:
        rx, ry = s[2] - s[1], s[4] - s[3]
        if rx <= 2.1 and ry <= 2.1 and rx > 1.0:
            s[5] = 1
        elif rx <= 1.1 and ry <= 1.1:
            s[5] = 2
        else:
            s[5] = 3
        _trace('cursor calibration: range=(%.2f,%.2f) conv=%d' % (rx, ry, s[5]))


def _left_down():
    try:
        import Keys
        return bool(BigWorld.isKeyDown(Keys.KEY_LEFTMOUSE))
    except Exception:
        return True


def _handle_mouse(event):
    if not _PANEL.get('visible'):
        return False
    px = _event_to_px(event)
    if px is None:
        return False
    if not _left_down():
        _CLICK_LOCK.clear()
        return False
    x, y = px
    for b in _BUTTONS:
        rx, ry, rw, rh = b['rect']
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            key = str(b['key'])
            if key in _CLICK_LOCK:
                return True
            _CLICK_LOCK.add(key)
            try:
                b['toggle']()
                _redraw_buttons()
                _save_filters()
                _trace('panel click: %s' % (b['key'],))
            except Exception as e:
                _trace('panel click error: %r' % (e,))
            return True
    return False


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
def _on_hotkey():
    if _in_battle():
        _trace('HOTKEY: in battle, skip')
        return
    now = time.time()
    if now - _LAST_TIME[0] < SELECT_COOLDOWN:
        _trace('HOTKEY: cooldown, skip')
        return
    _LAST_TIME[0] = now
    try:
        from helpers import dependency
        from skeletons.gui.shared import IItemsCache
        vehicles = dependency.instance(IItemsCache).items.getVehicles()
    except Exception as e:
        _trace('HOTKEY: vehicles error: %r' % (e,))
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
    _update_panel_visibility()
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
        from gui import g_mouseEventHandlers, g_guiResetters
        g_mouseEventHandlers.add(_handle_mouse)
        g_guiResetters.add(_on_gui_reset)
    except Exception as e:
        _trace('register handlers error: %r' % (e,))
    try:
        BigWorld.callback(POLL_INTERVAL, _tick)
        _trace('start: poll callback scheduled OK')
    except Exception as e:
        _POLL_ON[0] = False
        _trace('start: poll FAILED: %r' % (e,))


def _stop():
    _POLL_ON[0] = False
    try:
        from gui import g_mouseEventHandlers, g_guiResetters
        g_mouseEventHandlers.discard(_handle_mouse)
        g_guiResetters.discard(_on_gui_reset)
    except Exception:
        pass
    try:
        _save_filters()
    except Exception:
        pass
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


# 模块级双保险
_trace('module loaded, starting')
_load_config()
_load_filters()
_start()

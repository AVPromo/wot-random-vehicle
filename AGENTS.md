# AGENTS.md

供在此仓库工作的 AI 编码代理使用的指南。

## 概览

`mod_random_vehicle` 是一个 World of Tanks CN 客户端（2.3.x，Python 2.7 + BigWorld）的车库 MOD：按 F11 随机选择自己已拥有的一辆车。**合法合规约束**：只使用客户端已有数据，不做任何作弊功能（读取服务器未下发信息、自动瞄准、敌方装填等一律不实现）。

## 仓库结构

```
src/mod_random_vehicle.py       # MOD 源码(Python 2.7, 唯一的业务逻辑所在)
res/gui/mods/randomVehicle.xml  # 按键配置(KEY_F11)
build_wotmod.py                 # 构建+部署脚本(Python 3, 调用 py2.7 编译)
dist/mod_random_vehicle.wotmod  # 构建产物, 由 build_wotmod.py 生成
```

## 构建 / 部署

```bash
python build_wotmod.py --deploy [--version X.Y.Z.W] [--game-root PATH]
```

- 编译 `.pyc` 需要 Python 2.7（默认 `C:\Python27\python.exe`）
- `--deploy` 会把 wotmod 复制到 `<游戏根>/mods/<版本>/`，配置到 `res_mods/<版本>/gui/mods/`
- 版本号不传时自动从游戏 `paths.xml` 探测

## 不可违背的格式规则（改动 MOD 时）

| 规则 | 说明 |
|---|---|
| wotmod = 不压缩 zip | `ZIP_STORED`，压缩会加载失败 |
| `res/` 挂载根 | 脚本放 `res/scripts/client/gui/mods/`（**中间有 `gui`**） |
| 文件名 `mod_` 前缀 | 加载器只执行 `mod_*.pyc` |
| 必须 `.pyc` | `.py` 源码不执行；魔数必须 `03 f3 0d 0a`（标准 Python 2.7） |
| 版本目录 | 部署到 `<游戏根>/mods/<当前版本号>/`，客户端更新后需重新部署 |

## 业务 API（2.3.1.1，改动前先核实）

- **取车列表**：`IItemsCache`（`from skeletons.gui.shared import IItemsCache`，经 `helpers.dependency` 注入）→ `items.getVehicles()` 返回全科技树车辆，**必须过滤 `veh.isInInventory`** 才是自己拥有的车
- **选车**：`gui.shared.event_dispatcher.selectVehicleInHangar(intCD)`；`g_currentVehicle.selectVehicle(intCD)` 单独调用**不会**驱动车库切换
- **按键**：`BigWorld.isKeyDown(Keys.KEY_F11)` + `BigWorld.callback` 轮询

## 验证方法

- 改完必须 `build_wotmod.py --deploy`，用户重启游戏测试
- 排障看 `<游戏根>/mod_random_vehicle.debug` 和 `python.log`（搜 `[mod_random_vehicle]`）
- 不确定的 API 到 `res/packages/scripts.pkg` 里用 Python 2.7 `marshal`+`dis` 反汇编核实（项目里所有 API 均以此确认）
- 参考：`<游戏根>/mods/<版本>/` 下 zanju 的插件（研发进度条等）是正常工作的示例

## 提交规范

- 提交信息用中文或英文均可，说明改动意图
- 保持 `src/` 是唯一逻辑来源；`dist/` 由构建脚本生成，改逻辑不改它

# 坦克世界随机选车 MOD（mod_random_vehicle）

在车库按 **F11**（可改键）随机选中自己的一辆战车。纯客户端功能，等同替你点击车辆，不读取服务器未下发信息，不含任何作弊逻辑。

## 目录结构

```
wot-random-vehicle/
├── src/mod_random_vehicle.py       ← 源码(Python 2.7)
├── res/gui/mods/randomVehicle.xml  ← 按键配置
├── build_wotmod.py                 ← 构建+部署脚本
├── dist/mod_random_vehicle.wotmod  ← 构建产物(游戏加载的包)
└── README.md
```

## 部署

```bash
python build_wotmod.py --deploy        # 构建并自动部署到当前版本目录
python build_wotmod.py --deploy --version 2.3.1.1   # 指定版本
```

部署后文件位置：

```
<游戏根>/mods/<版本号>/mod_random_vehicle.wotmod      ← 主 MOD
<游戏根>/res_mods/<版本号>/gui/mods/randomVehicle.xml ← 按键配置
```

重启游戏即可。改键编辑 `randomVehicle.xml` 的 `<key>`（如 `KEY_F10` / `KEY_F12`，对应 `Keys` 模块常量名）。

## 排障

游戏根目录会生成 `mod_random_vehicle.debug`（分步日志）。`python.log` 里搜 `[mod_random_vehicle]`。出现 `HOTKEY: select result=True` 但车没切换 = 选车 API 版本不匹配，看下面的适配说明。

## 版本适配注意事项（重要，都是实测踩坑记录）

这是 CN 客户端 **2.3.x**（2026）特有的 MOD 机制，与传统 WOT（1.x）差异很大：

1. **客户端版本目录会变**：`paths.xml` 指向哪个版本号，MOD 就放哪个 `mods/<版本>/` 目录。客户端更新后必须重新部署（`build_wotmod.py --deploy` 会自动探测版本号）。错误现象：`mods/2.3.1.0/` 里明明有 MOD 却不生效，因为客户端已是 2.3.1.1。

2. **散装 `.py` 不再被加载**：`res_mods/<版本>/scripts/client/mods/*.py` 在这个客户端**不执行**（传统机制已移除，`scripts/client/mods/` 在脚本包里 0 引用）。只能用 wotmod 包。

3. **wotmod 格式要求**：
   - 必须是**不压缩**的 zip（`ZIP_STORED`）
   - 根目录必须有 **`res/` 挂载根**，脚本放 `res/scripts/client/gui/mods/`（注意中间有 `gui`）
   - 文件名必须以 **`mod_`** 开头（如 `mod_random_vehicle.pyc`），加载器只执行 `mod_*.pyc`
   - 加载失败时日志报 `Mod package ... load error: mod is empty or dont have mount root`

4. **脚本必须编译为 `.pyc`**：原生加载器只执行 `.pyc`（`.py` 即使路径正确也不执行）。字节码魔数必须是标准 Python 2.7 的 `03 f3 0d 0a`（用官方 Python 2.7.18 编译即可）。

5. **模块接口**：提供 `init()`/`fini()`（或 `finit()`）会被加载器调用；但**模块顶层代码在导入时就会执行**（sixthsense 插件就是纯顶层代码）。本 MOD 顶层 + init 双保险启动。

6. **关键 API（2.3.1.1）**：
   - 车辆列表：`dependency.instance(IItemsCache).items.getVehicles()` 返回**全科技树**所有车辆（含未购买），必须过滤 `isInInventory` 才是自己拥有的车
   - 选车：`from gui.shared.event_dispatcher import selectVehicleInHangar; selectVehicleInHangar(intCD)`（官方 API，反汇编确认：派发 `SELECT_VEHICLE_IN_HANGAR` 事件 → `g_currentVehicle.selectVehicle` → `showHangar`）。单独调 `g_currentVehicle.selectVehicle(intCD)` **不会**驱动车库换车
   - `skeletons.items_cache` 在 2.3.1.1 已移除，`IItemsCache` 在 `skeletons.gui.shared`

7. **可参考的正常插件**：`mods/<版本>/zanju.researchprogressbar_1.3.1.wotmod`（研发进度条）、`sixthsense_core.wotmod`（第六感）——它们的内部结构就是标准答案。

## 卸载

删除 `mods/<版本>/mod_random_vehicle.wotmod` 和 `res_mods/<版本>/gui/mods/randomVehicle.xml` 即可。

## 合规声明

- 只使用客户端已有数据（自己车库列表），无自动瞄准/预判/敌方装填等作弊逻辑
- 等同于替玩家在车库点击车辆

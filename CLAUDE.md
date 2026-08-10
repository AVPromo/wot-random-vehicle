# CLAUDE.md

本文件为 Claude Code 在该仓库工作时的指南。

## 项目是什么

坦克世界（World of Tanks）CN 客户端 2.3.x 的车库 MOD：按 F11（可改键）随机选中自己的一辆战车。纯客户端功能，等同替玩家在车库点击车辆，**不包含任何作弊逻辑**（无服务器数据读取、无自动瞄准、无敌方装填等）。

## 技术环境

- **MOD 运行环境**：客户端内置 Python 2.7 + BigWorld（`scripts.pkg` 里的字节码魔数 `03 f3 0d 0a`）
- **构建工具**：仓库脚本用 Python 3（`python build_wotmod.py`），编译 `.pyc` 需要本机 Python 2.7（默认 `C:\Python27\python.exe`）
- **游戏目录**：`C:/Games/World_of_Tanks_CN`（当前客户端版本 2.3.1.1，随时会变）

## 常用命令

```bash
python build_wotmod.py              # 仅构建 dist/mod_random_vehicle.wotmod
python build_wotmod.py --deploy     # 构建 + 自动部署到当前版本目录(自动探测版本号)
python build_wotmod.py --deploy --version 2.3.1.1 --game-root "C:/Games/World_of_Tanks_CN"
```

## 关键约束（改动时必须遵守，都是实测踩坑结论）

1. **散装 `.py` 不加载**：`res_mods/<版本>/scripts/client/mods/*.py` 在 2.3.x 不执行。必须用 wotmod 包。
2. **wotmod 三要素**：不压缩 zip（`ZIP_STORED`）+ 根目录 `res/` 挂载根 + 脚本放 `res/scripts/client/gui/mods/`（中间有 `gui`）。
3. **文件名 `mod_` 前缀 + `.pyc`**：加载器只执行 `mod_*.pyc`（`.py` 不执行）。用 `build_wotmod.py` 编译，魔数必须为 `03 f3 0d 0a`。
4. **模块接口**：提供 `init()`/`fini()`/`finit()`（加载器会调用），但顶层代码在导入时即执行，两者双保险。
5. **关键 API（2.3.1.1）**：
   - 车辆列表：`dependency.instance(IItemsCache).items.getVehicles()` 返回**全科技树**车辆（含未购买），必须过滤 `isInInventory`
   - 选车：`gui.shared.event_dispatcher.selectVehicleInHangar(intCD)`（官方 API）。单独调 `g_currentVehicle.selectVehicle(intCD)` 不会驱动车库换车
   - `IItemsCache` 在 `skeletons.gui.shared`（`skeletons.items_cache` 已被移除）
6. **客户端版本目录会变**：MOD 放 `<游戏根>/mods/<版本号>/`。更新版本后必须重新部署。

## 测试与调试

- 排障看游戏根目录的 `mod_random_vehicle.debug`（源码里的 `_trace` 写入）和 `python.log` 里的 `[mod_random_vehicle]`
- 改动源码后必须重新 `python build_wotmod.py --deploy` 并让用户重启游戏验证
- 用户可能在其他客户端版本目录装 MOD（如 `mods/2.3.0.0/`），改 API 前先在 `scripts.pkg` 字节码里核实

## 游戏内 API 逆向技巧

游戏脚本打包在 `C:/Games/World_of_Tanks_CN/res/packages/scripts.pkg`（BigWorld 二进制包）。可以用 Python 2.7 `marshal.loads` 加载其中的 `.pyc` 并 `dis` 反汇编，确认 API 签名/行为（本项目所有 API 都这样核实过）。参考包：`<游戏根>/mods/<版本>/zanju.researchprogressbar_*.wotmod` 是正常工作的插件，其内部结构是标准答案。

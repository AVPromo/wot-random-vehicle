# 安装部署指南

本 MOD 用于 **WOT CN 客户端 2.3.x**。安装只需要把两个文件放进游戏目录对应的版本文件夹。

## 需要哪些文件

| 文件 | 作用 | 必需 |
|---|---|---|
| `mod_random_vehicle.wotmod` | MOD 主程序（内含编译好的 `mod_random_vehicle.pyc`） | ✅ 必需 |
| `randomVehicle.xml` | 按键配置（默认 F11，可改） | ✅ 建议（没有则用默认 F11） |

> 仓库里的 `src/mod_random_vehicle.py` 是源码（开发用，不进游戏）；`dist/mod_random_vehicle.wotmod` 和 `res/gui/mods/randomVehicle.xml` 才是安装所需的成品。

## 放到哪个目录

把文件放进**当前客户端版本号**对应的目录（版本号以游戏根目录 `paths.xml` 为准，升级后版本号会变）：

```
<游戏根>/                             例如 C:/Games/World_of_Tanks_CN/
├── mods/
│   └── 2.3.1.1/
│       └── mod_random_vehicle.wotmod     ← MOD 放这里(版本号目录)
└── res_mods/
    └── 2.3.1.1/
        └── gui/
            └── mods/
                └── randomVehicle.xml     ← 配置放这里(需新建 gui/mods 子目录)
```

**注意**：
- 版本号目录必须和客户端**当前**版本完全一致（看 `paths.xml`，不是看文件夹哪个最新）
- `mods/` 里放 `.wotmod` 包，`res_mods/` 里放配置/资源，两者都要有
- 客户端升级后（如 2.3.1.1 → 2.3.2.0）需要重新安装到新版本目录

## 安装方式

### 方式一：双击一键安装（推荐）

```
双击 install_wotmod.bat      ← 安装预构建的成品(无需编译, 最快)
双击 build_and_deploy.bat   ← 重新编译+打包+安装(改过源码后用)
```

脚本会自动定位游戏目录和当前版本号，装完按任意键关闭。找不到游戏时用命令行指定：

```
install_wotmod.bat --game-root "C:/Games/World_of_Tanks_CN"
```

### 方式二：命令行

```bash
# 安装预构建成品
python install_wotmod.py --game-root "C:/Games/World_of_Tanks_CN"

# 构建 + 安装
python build_wotmod.py --deploy

# 手动指定版本(自动探测失败时)
python build_wotmod.py --deploy --version 2.3.1.1 --game-root "C:/Games/World_of_Tanks_CN"
```

### 方式三：手动复制（跨机器/应急）

1. 复制 `dist/mod_random_vehicle.wotmod` → `<游戏根>/mods/<版本号>/`
2. 复制 `res/gui/mods/randomVehicle.xml` → `<游戏根>/res_mods/<版本号>/gui/mods/`（`gui/mods` 目录不存在则新建）
3. 启动游戏验证

## 改键

编辑 `res_mods/<版本号>/gui/mods/randomVehicle.xml`：

```xml
<key>KEY_F11</key>    ← 改成 KEY_F10 / KEY_F12 等(Keys 模块常量名)
```

## 筛选随机池（配置文件方式）

F11 随机选车时，只从符合 `randomVehicle.xml` 里 `<filters>` 条件的车中随机。配置文件**运行时实时读取**：保存后约 1 秒内自动生效，无需重启游戏。也可用 `install_gui.py` 里的"MOD 配置"面板图形化修改。

```xml
<filters>
    <!-- 金币车: 0=不限  1=只要金币车  2=只要银币车 -->
    <premiumMode>0</premiumMode>

    <!-- 坦克类型, 逗号分隔多选, 留空=全部:
         lightTank 轻坦 / mediumTank 中坦 / heavyTank 重坦 /
         AT-SPG 坦克歼击车 / SPG 自行火炮 -->
    <classes></classes>

    <!-- 国家(数字ID), 逗号分隔, 留空=全部:
         0=苏 1=德 2=美 3=法 4=英 5=中 6=日 7=捷 8=瑞 9=波 10=意 -->
    <nations></nations>

    <!-- 等级 1~10, 逗号分隔, 留空=全部 -->
    <tiers></tiers>
</filters>
```

示例——只要中国和苏联的 8~10 级重坦+中坦（含金币车）：

```xml
<filters>
    <premiumMode>0</premiumMode>
    <classes>heavyTank,mediumTank</classes>
    <nations>5,0</nations>
    <tiers>8,9,10</tiers>
</filters>
```

示例——只要 10 级银币车：

```xml
<filters>
    <premiumMode>2</premiumMode>
    <tiers>10</tiers>
</filters>
```

## 验证是否装好

1. 启动游戏 → 进入车库
2. 按 F11，应随机切换到你自己的一辆车（每次按换一辆）
3. 排障：游戏根目录出现 `mod_random_vehicle.debug` 文件 = MOD 已加载；`python.log` 搜 `[mod_random_vehicle]`

## 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| 完全无反应 | 版本目录不对 | 确认 `paths.xml` 里的版本号，重新安装到对应目录 |
| 无反应 + 日志无 `mod_*.pyc` | wotmod 没被加载 | 确认是"不压缩"zip、带 `res/` 挂载根（用本仓库脚本生成就正确） |
| 按 F11 切到未拥有的车 | 旧版 MOD | 重新用最新版 `build_and_deploy.bat` 部署 |
| 想卸载 | — | 删除上面两个文件即可 |

## 部署原理（为什么是这两个位置）

- `mods/<版本>/` 在游戏 `paths.xml` 中注册为 `mask="*.wotmod"` 的资源路径，游戏启动时挂载其中的 wotmod 并执行 `res/scripts/client/gui/mods/mod_*.pyc`
- `res_mods/<版本>/` 是最高优先级的资源覆盖层，MOD 直接读取其中的 `gui/mods/randomVehicle.xml` 物理文件，并每秒检查 mtime，变化即热重载

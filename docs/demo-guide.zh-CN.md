# Demo 开发、调试、发布与运行指南

本文以 `samples/dotnet` 为例，介绍如何使用官方 Godot .NET 编辑器开发 C#，并通过 LeanCLR 发布到 Windows x64、HTML5 和 Android x86_64。样例显示一个蓝色圆点，使用键盘左右方向键移动。

编辑器中的运行和调试使用官方 .NET 后端；发布后的游戏使用 LeanCLR。当前发布适配器面向仓库内样例，其他项目可能需要增加适配，兼容范围见 [README](../README.md)。

## 1. 准备环境

以下命令使用 Windows PowerShell，并从仓库根目录开始执行。

首次获取仓库：

```powershell
git clone --recurse-submodules https://github.com/focus-creative-games/leanclr-godot.git
cd leanclr-godot
```

已有工作目录则在仓库根目录初始化依赖：

```powershell
git submodule update --init --recursive
```

准备官方 Godot 4.7.2 .NET 编辑器、.NET SDK 10 和匹配的 BCL，以及发布工具链。发布还需要固定版本的 Godot 源码、私有 headless 导出器和目标平台工具链；克隆仓库不会自动准备这些依赖。完整版本和准备要求见 [发布 SDK](publication-sdk.md)。

在 PowerShell 中设置仓库和编辑器变量：

```powershell
$repo = (Get-Location).Path
$mono = $env:GODOT_DOTNET_EXE
```

请先将环境变量 `GODOT_DOTNET_EXE` 设置为官方 Godot .NET 编辑器可执行文件的实际路径；也可以直接给 `$mono` 赋值。Windows 建议选择带控制台的编辑器可执行文件，以便查看日志。后续命令均在此 PowerShell 会话中执行，工作目录保持为 `$repo`。

| 工程 | 用途 |
| --- | --- |
| `samples/dotnet` | 主要试玩与开发示例，建议从这里开始 |
| `samples/semantics` | 对象、信号、资源、集合等语义示例 |
| `samples/extended` | 扩展 API 与 GC 压力验证示例 |

## 2. 开发与运行

使用官方 .NET 编辑器打开样例：

```powershell
& $mono --editor --path "$repo\samples\dotnet"
```

也可以在编辑器项目管理器中导入仓库内的 `samples/dotnet/project.godot`。

1. 等待资源导入完成。
2. 保存代码和场景，点击编辑器的 C# 构建按钮。
3. 按 **F5** 运行主场景，点击游戏窗口后使用 **← / →** 移动圆点。
4. 按 **F8** 停止游戏。

开发工程保留现有 `net8.0` 配置，发布工具会独立构建所需程序集，无需手动更改开发工程的目标框架。

主要文件：

| 文件 | 内容 |
| --- | --- |
| `samples/dotnet/Player.cs` | Node2D 生命周期、输入和绘制 |
| `managed/DemoLogic/Motion.cs` | 共享位移逻辑和计算基准；当前混合 AOT 编译其中两个方法 |
| `samples/dotnet/Main.tscn` | 场景和导出属性 |

场景中的 `Speed` 属性会覆盖脚本默认值。要调整速度，在 Inspector 中修改 Player 节点的 Speed 并保存场景。

修改 C# 后，按“停止游戏 → 保存修改 → 构建 → F5”的顺序操作。也可从命令行构建：

```powershell
dotnet build "$repo\samples\dotnet\Gameplay.csproj" -c Debug --nologo
```

等待编辑器完成 DLL 更新和资源扫描后重新运行。编辑器开发不需要重建 LeanCLR 模板。

发布前同样要完成官方工程的构建和导入，发布工具会复用开发工程的脚本元数据。如果该工程的 GUI 编辑器已关闭，可以在构建后通过命令行导入：

```powershell
& $mono --headless --editor --path "$repo\samples\dotnet" --import
```

## 3. C# 断点调试

以 Visual Studio 为例：

1. 打开 `samples/dotnet/Gameplay.sln`，选择 Debug 构建配置。
2. 在 `Player.cs` 的 `_Process` 方法中设置断点。
3. 从官方 Godot .NET 编辑器按 F5 启动游戏。
4. 在 Visual Studio 中选择“调试 → 附加到进程”，选择游戏子进程，使用托管 .NET / CoreCLR 调试类型。
5. 断点命中后，查看 `Position`、`Speed`、`direction` 等变量，或进行单步调试。

游戏和编辑器可能使用相同的 EXE 名称，可通过 PID、父进程和命令行区分。每次重新启动游戏，都需要附加到新的游戏进程。

附加到运行中的游戏时，首次 `_Ready` 已经执行。调试启动早期代码需要配置 IDE 从启动时调试 Godot。Godot 自带的脚本调试窗口不能替代 C# IDE 的托管断点调试。

以上流程适用于官方 .NET 开发进程。LeanCLR 发布包当前通过日志和发布报告诊断。

## 4. 发布 LeanCLR 版本

先完成开发工程的构建与导入，并准备好发布工具链。以下输出目录是用户自行生成的正式发布目录，不依赖预先构建的样例包。

为每轮发布选择新的输出目录：

```powershell
Set-Location $repo
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = "build/release/$stamp"
```

输出目录必须位于仓库内、不能位于 `samples` 内，且不能已经存在。依次执行各目标的发布命令，SDK 不允许同时发布多个目标。

以下命令使用 `--build` 构建混合 AOT 模板。已有匹配模板时可省略 `--build`。

### Windows x64

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --build --output "$out/win64"
```

### HTML5

```powershell
python tools/publish.py --target html5 --sample samples/dotnet --aot --build --output "$out/html5"
```

### Android x86_64

```powershell
python tools/publish.py --target android --sample samples/dotnet --aot --build --output "$out/android"
```

当前 Android 发布产物为 MuMu x64 使用的调试 APK。ARM64、真机、AAB 和商店签名尚未验证。

### 发布选项

| 选项 | 使用时机 |
| --- | --- |
| 不加 `--aot` | 使用纯解释模板 |
| `--aot` | 使用混合模式；当前仅编译 DemoLogic 的两个方法，其余继续解释执行 |
| `--build` | 首次构建、模板缓存缺失，或需要更新编译进模板的代码 |
| `--experimental` | 修改了样例源码、场景、资源，或使用尚未登记的源码配置 |
| `--smoke` | 生成会自动退出的 Android 测试包；普通试玩发布时省略 |

每次发布都会重新构建托管程序集。复用模板仍会加载本次构建的 Gameplay DLL。

### 修改项目后重新发布

SDK 默认只接受已验证的精确样例配置。修改源码、场景或资源后，即使只调整了 Speed，也需要加 `--experimental` 并补充运行测试。

只修改 `Player.cs`、场景或资源，且已有匹配的混合 AOT 模板时，例如：

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --experimental --output "$out/win64-edited"
```

如果修改了 `managed/DemoLogic/Motion.cs`，还需要重建混合 AOT 模板：

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --build --experimental --output "$out/win64-logic"
```

其他目标使用对应的 `--target`。每次执行都要选择尚不存在的输出目录。`--experimental` 允许发布待验证配置，仍会拒绝已知不支持的依赖；新 API、项目布局或依赖可能需要额外适配。

### 可选：编辑器发布菜单

```powershell
python tools/install-editor-addon.py samples/dotnet
```

重新打开工程或确认插件已启用后，可在“项目 → 工具”中使用三个 `LeanCLR: Publish ...` 菜单项。菜单使用解释模板，需要 AOT、重建模板或实验模式时使用命令行。发布在独立进程中执行，结果路径打印到编辑器输出。

LeanCLR 发布入口为上述工具或插件菜单。官方编辑器原生的 .NET Export 使用其自身的发布流程。

## 5. 运行发布包

仅运行发布包时，无需重新编译 Godot。下面的路径对应第 4 节生成的输出；使用已有发布包时，将路径替换为该包所在目录。

### Windows x64

```powershell
& "$repo\$out\win64\leanclr-node2d.console.exe"
```

也可双击发布目录中的 `leanclr-node2d.exe`。聚焦游戏窗口后使用左右方向键。复制或分发时保留整个发布目录，包括 EXE 对应的 PCK。

控制台中可查看 LeanCLR 初始化和运行日志，例如：

```text
LEANCLR_GODOT_READY backend=LeanCLR script_language=CSharpScript
```

### HTML5

在 PowerShell 中启动本地 HTTP 服务：

```powershell
python -m http.server 8060 --bind 127.0.0.1 --directory "$out/html5"
```

保持终端运行，用 Chrome 打开 [本地试玩页面](http://127.0.0.1:8060/index.html)。等待加载，点击画布后使用左右方向键。首次加载需要下载并编译 Wasm。

发布目录中的 HTML、JS、Wasm、PCK 等文件需放在一起，并通过 HTTP 服务访问。浏览器 F12 的 Console 和 Network 可用于排查加载问题。普通试玩地址省略 `?smoke`，该参数会启用自动退出的测试流程。体验结束后按 `Ctrl+C` 停止服务，再继续执行其他命令。

### Android：安装到 MuMu x64

准备 Android SDK Platform-Tools 并将 `adb` 加入 PATH。启动 MuMu x64 后设置 ADB 连接地址；以下为常见示例，请按模拟器配置调整：

```powershell
$adb = (Get-Command adb).Source
$device = 'localhost:7555'
& $adb connect $device
& $adb devices
```

确认列表中对应设备状态为 `device`，再安装和启动：

```powershell
& $adb -s $device install -r "$repo\$out\android\demo.apk"
& $adb -s $device shell am start -W -n 'com.focuscreative.leanclrgodot.dotnet/com.godot.game.GodotAppLauncher'
```

也可从模拟器桌面启动 `LeanCLR dotnet`。这里的包名和启动组件对应未修改的 `samples/dotnet` 工程；修改应用标识后需相应更新启动命令。

样例没有触屏方向按钮，需要模拟器将键盘左右键传给游戏。查看引擎日志：

```powershell
& $adb -s $device logcat -s godot
```

按 `Ctrl+C` 停止日志查看。命令中的 `-s $device` 用于明确选择目标设备。

## 6. 常见问题与发布报告

| 现象 | 处理 |
| --- | --- |
| `development script metadata is missing` | 先用官方 .NET 编辑器构建并导入工程 |
| C# 断点为空心、无法命中 | 确认附加到游戏子进程，使用 Debug 构建和对应符号；游戏重启后重新附加 |
| `Output must be a new directory` | 更换输出目录，或重新生成 `$stamp` 和 `$out` |
| `experimental-pending` / `Publication rejected` | 查看 `compatibility.json`；修改过的配置需要 `--experimental`，明确不支持的调用需要调整代码 |
| `AOT assembly mismatch` | AOT 业务库变化后，使用对应目标的 `--aot --build --experimental` 重建 |
| 模板缓存缺失或版本 / GodotSharp 不匹配 | 使用对应目标的 `--build` 重建，查看 `pipeline.log` 获取详细诊断 |
| `Another LeanCLR publication is active` | 等前一个发布进程完成后再执行 |
| Web 无法加载或黑屏 | 确认通过 HTTP 访问完整发布目录，查看浏览器 Console 和 Network |
| Android 启动后立即退出 | 确认发布时省略了 `--smoke`，并用 `adb logcat -s godot` 查看错误 |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 检查签名是否一致，优先复用原 debug keystore；卸载重装会删除应用数据 |

成功发布目录包含 `publication.json`、`compatibility.json` 和 `artifacts.json`，分别记录发布依赖、兼容性与产物信息。发布失败时，工具会保留输出目录旁的 staging 目录和 `pipeline.log` 等诊断文件；可按终端提示定位日志。

更多发布选项、检查规则和报告格式见 [发布 SDK](publication-sdk.md)。

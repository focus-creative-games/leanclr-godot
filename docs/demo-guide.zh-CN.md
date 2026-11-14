# Demo 体验、开发调试与发布操作说明

本文针对当前这台 Windows 开发机和已经构建好的仓库。开发时使用官方 Godot .NET 编辑器；下面的发布命令使用私有导出工具和 LeanCLR 模板，不会替换官方编辑器。

## 1. 准备 PowerShell 环境

打开 PowerShell，先执行：

```powershell
$repo = 'D:\workspace\wasmclr\hosts\godot\leanclr-godot'
$mono = 'D:\workspace\wasmclr\hosts\godot\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe'
$adb = Join-Path $repo '.tools\android-sdk\platform-tools\adb.exe'
Set-Location $repo
```

后面的命令均假设当前目录是 `$repo`，且这些变量已定义。当前机器已准备好发布依赖和三平台模板，体验现成包不需要重新编译 Godot。

| 工程 | 用途 | 运行表现 |
| --- | --- | --- |
| `samples/dotnet/project.godot` | 主要试玩和开发工程 | 蓝色圆点，左右方向键水平移动 |
| `samples/semantics/project.godot` | 对象、信号、资源、集合等 15 项契约 | 输出 `M2_SEMANTICS_OK` 后自动退出 |
| `samples/extended/project.godot` | 扩展 API 与大堆 GC 的 11 项契约 | 输出 `M5_EXTENDED_OK` 后自动退出；会申请 160 MiB 测试数据 |

第一次体验请打开 `samples/dotnet`，不是仓库根目录。

## 2. 先试玩现成的 LeanCLR 发布包

### Win64

```powershell
& "$repo\build\export\m5\aot-v3\leanclr-node2d.console.exe"
```

也可以直接双击同目录的 `leanclr-node2d.exe`。点击游戏窗口使其获得焦点，然后按 **← / →** 移动圆点。关闭再启动会重置位置。

控制台应能看到：

```text
LEANCLR_GODOT_READY backend=LeanCLR script_language=CSharpScript
LEANCLR_AOT_HOTCALL module=DemoLogic step=4 benchmark=0
```

普通试玩不加 `--m0-smoke` 或 `--profile`，否则程序会在指定帧数后退出。复制给别的目录运行时，保留整个发布目录，尤其是 EXE 对应的 PCK；不要只复制 EXE。

### HTML5

在一个单独的 PowerShell 窗口执行：

```powershell
Set-Location 'D:\workspace\wasmclr\hosts\godot\leanclr-godot'
python -m http.server 8060 --bind 127.0.0.1 --directory build/export/m5/web-v3
```

保持这个终端运行，用 Chrome 打开：

```text
http://127.0.0.1:8060/index.html
```

等待加载，点击画布，再按 **← / →**。首次加载需要下载和编译 Wasm。用 `Ctrl+C` 停止 HTTP 服务。

要通过 HTTP 服务打开整个目录，不要双击 HTML。不要给普通试玩地址加 `?smoke`；这个参数会启用四帧自动测试并退出。浏览器 F12 的 Console 中可查看 LeanCLR 日志。

### Android：安装到本机 MuMu

先启动 MuMu，再在第 1 节的 PowerShell 窗口执行：

```powershell
& $adb connect localhost:7555
& $adb devices
& $adb -s localhost:7555 install -r "$repo\build\export\m5\android-playable\demo.apk"
& $adb -s localhost:7555 shell am start -W -n 'com.focuscreative.leanclrgodot.dotnet/com.godot.game.GodotAppLauncher'
```

也可以从 MuMu 桌面点击 `LeanCLR dotnet`。应显示蓝色圆点，应用不会自动退出。这个 APK 是本轮已验收的 **Android x86_64 调试包**。

当前 demo 没有触屏方向按钮，玩法输入是键盘左右键；在 MuMu 上手动移动需要模拟器将相应键盘事件传给游戏。部署和渲染可以直接体验；需要确定性移动验证时，使用后面的 Android smoke 流程，它会由 C# 自动按下动作并核对位置。

查看本应用引擎日志：

```powershell
& $adb -s localhost:7555 logcat -s godot
```

用 `Ctrl+C` 结束日志查看。后续 ADB 命令都带 `-s localhost:7555`，避免机器上存在多个设备时选错目标。

## 3. 在官方 Godot .NET 编辑器中开发和调试

### 打开工程并运行

```powershell
& $mono --editor --path "$repo\samples\dotnet"
```

也可以在这个官方 .NET 编辑器的项目管理器中导入：

```text
D:\workspace\wasmclr\hosts\godot\leanclr-godot\samples\dotnet\project.godot
```

1. 等待资源导入完成。
2. 保存场景和代码，点击编辑器的 C# 构建按钮；也可使用下面的 `dotnet build`。
3. 在 Godot 中按 **F5** 运行主场景。
4. 聚焦游戏窗口，使用左右方向键。
5. 在 Godot 中按 **F8** 停止游戏。

这里运行的是官方 .NET 后端，尚未使用 LeanCLR。开发工程保持现有 `net8.0` 配置；发布工具会在私有目录构建所需的发布程序集，不需要手动把开发工程改成 `net10.0`。

主要代码位置：

| 文件 | 内容 |
| --- | --- |
| `samples/dotnet/Player.cs` | Node2D 生命周期、输入、绘制、测试开关 |
| `managed/DemoLogic/Motion.cs` | 共享的位移函数和计算基准；混合发布中这两个方法由 LeanAOT 编译 |
| `samples/dotnet/Main.tscn` | 场景和导出属性；当前 `Speed = 120` |

场景里的 `Speed = 120` 会覆盖 `Player.cs` 中的默认值 60。要试不同速度，选中场景里的 Player 节点，在 Inspector 修改 Speed 并保存场景。

### 修改 C# 后重新 Play

按“停止游戏 → 保存修改 → 构建 → F5”的顺序操作：

```powershell
dotnet build "$repo\samples\dotnet\Gameplay.csproj" -c Debug --nologo
```

等待官方编辑器完成 DLL 更新和资源扫描后重新 Play。这个流程会加载新 DLL；不用重建 LeanCLR 模板。发布前也要完成官方工程的构建和导入，因为私有导出工具会使用开发工程的脚本元数据。

如果完全使用命令行，并且该工程的 GUI 编辑器已经关闭，可以显式执行导入：

```powershell
& $mono --headless --editor --path "$repo\samples\dotnet" --import
```

### C# 断点调试：以 Visual Studio 为例

1. 用 Visual Studio 打开 `samples/dotnet/Gameplay.sln`，确保使用 Debug 构建配置。
2. 在 `Player.cs` 的 `_Process` 方法内设置断点。
3. 从官方 Godot .NET 编辑器 F5 启动游戏，让游戏保持运行。
4. 在 Visual Studio 选择“调试 → 附加到进程”，选择 **游戏子进程**，使用托管 .NET / CoreCLR 调试类型。
5. 游戏与编辑器可能使用相同的 Godot EXE 名称。用 PID、父进程和命令行区分，不要附加到项目管理器或编辑器进程。
6. 断点命中后，可以查看 `Position`、`Speed`、`direction` 等值，并在 IDE 中单步和继续。

附加到运行中的进程时，首次 `_Ready` 已经执行，所以先用 `_Process` 验证断点。若要调试启动早期代码，需要另外配置 IDE 从启动时调试 Godot。Godot 自带的脚本调试窗口不能替代 C# IDE 的托管断点调试。

这套 .NET 调试流程用于开发进程。LeanCLR 发布包当前通过日志、确定性测试和发布报告诊断，不使用 CoreCLR 调试器调试其解释器或 AOT 代码。

## 4. 自己重新发布三平台

先完成第 3 节的官方构建和导入。下面使用当前已构建好的混合 AOT 模板，因此不用加 `--build`。

每轮发布先生成一个新输出前缀：

```powershell
Set-Location $repo
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = "build/experience/$stamp"
```

输出目录必须位于仓库内、不能位于 samples 内，且不能已经存在。按顺序执行发布，SDK 会拒绝同时发布两个目标。

### Win64 发布和运行

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --output "$out/win64"
& "$repo\$out\win64\leanclr-node2d.console.exe"
```

### HTML5 发布和运行

```powershell
python tools/publish.py --target html5 --sample samples/dotnet --aot --output "$out/html5"
python -m http.server 8061 --bind 127.0.0.1 --directory "$out/html5"
```

在 Chrome 打开 `http://127.0.0.1:8061/index.html`。保留生成的 HTML、JS、Wasm、PCK 等文件在同一个目录。HTTP 服务占用该终端，结束后按 `Ctrl+C`。

### Android 发布、安装和运行

体验完上面的 HTML5 后，按 `Ctrl+C` 停止 HTTP 服务，在同一个 PowerShell 中继续执行，之前定义的变量仍然有效：

```powershell
python tools/publish.py --target android --sample samples/dotnet --aot --output "$out/android"
& $adb connect localhost:7555
& $adb -s localhost:7555 install -r "$repo\$out\android\demo.apk"
& $adb -s localhost:7555 shell am start -W -n 'com.focuscreative.leanclrgodot.dotnet/com.godot.game.GodotAppLauncher'
```

普通试玩发布 **不加 `--smoke`**。当前产物是给 MuMu x64 使用的 debug APK，不是 ARM64 真机包或商店 AAB。

### 发布选项如何选

| 选项 | 使用时机 |
| --- | --- |
| 不加 `--aot` | 使用纯解释模板，可用于对照体验 |
| `--aot` | 使用混合模式；当前只将 DemoLogic 的两个方法编译成原生代码，其余继续解释 |
| `--build` | 缓存模板不存在，或需要重新编译对应引擎模板；当前机器首次体验无需使用 |
| `--experimental` | 修改了样例源码、场景、资源，或使用尚未登记的源码配置 |
| `--smoke` | Android 四帧自动验证包，会自动退出；不是试玩包 |

每次发布都会重编译私有托管程序集。复用模板不表示复用旧 Gameplay DLL。

## 5. 改过代码以后如何发布

当前 SDK 默认只接受已经执行过测试的精确样例配置。即使只修改了场景中的 Speed，发布也会变成待验证配置，需要显式使用实验模式。

只改 `Player.cs`、场景或资源，且未改 AOT 业务库时，例如：

```powershell
# 先在官方编辑器完成构建、导入和 Play 验证，再发布。
python tools/publish.py --target win64 --sample samples/dotnet --aot --experimental --output "build/experience/edited-$stamp-win64"
```

如果修改了 `managed/DemoLogic/Motion.cs`，混合模板中编译进去的代码也必须更新：

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --build --experimental --output "build/experience/logic-$stamp-win64"
```

HTML5 和 Android 同样使用各自的 `--target` 重新 `--build`。否则会得到 `AOT assembly mismatch`，不能用修改后的 DLL 配旧 AOT 模板。

`--experimental` 只表示允许发布待验证的配置，仍会阻止明确不支持的调用，也不代表新增 API 已通过验收。新的项目布局、依赖或构造方式可能还需要扩展当前样例适配器。

可选的编辑器菜单安装方式：

```powershell
python tools/install-editor-addon.py samples/dotnet
```

重新打开工程或确认插件已启用后，在“项目 → 工具”中可见三个 `LeanCLR: Publish ...` 菜单项。当前菜单使用解释模板，不带 `--aot`、`--build` 或 `--experimental`；需要这些选项时使用命令行。发布仍交给独立进程，结果路径会打印到编辑器输出中。

不要把官方编辑器原生的 .NET Export 流程当作这里的 LeanCLR 发布入口。

## 6. 可选：自动验证

以下自动测试面向未修改的基准样例；改过速度或逻辑后，固定的 `x=8`、`speed=120` 等断言可能不再成立。

Win64 的四帧测试：

```powershell
& "$repo\build\export\m5\aot-v3\leanclr-node2d.console.exe" --headless -- --m0-smoke
```

成功标记：

```text
NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120
```

HTML5 的自动测试地址为 `http://127.0.0.1:8060/index.html?smoke`，在 F12 Console 查看同样的成功标记。需要自动启动真实浏览器、刷新和检查 AOT 入口时：

```powershell
python tools/test-web-runtime.py --directory build/export/m5/web-v3 --expected 'NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120' --require-aot --report-dir build/experience/web-check
```

Android 的四帧包已经存在：

```powershell
python tools/test-android-runtime.py build/export/m5/android-v3/demo.apk --require-aot --report-dir build/experience/android-check
```

它会安装测试 APK、运行三个独立进程并检查日志。因为包名与试玩版相同，测试会覆盖已安装的试玩 APK；测试后重新安装第 2 节的 `android-playable/demo.apk` 即可恢复普通试玩。

要验证试玩包的绘制、前后台恢复和进程重建：

```powershell
python tools/test-android-lifecycle.py build/export/m5/android-playable/demo.apk
```

这个脚本最后会停止应用，之后可以在 MuMu 桌面手动启动。

## 7. 失败时查看什么

| 现象 | 处理 |
| --- | --- |
| `development script metadata is missing` | 先使用官方 .NET 编辑器构建并导入该工程 |
| C# 断点是空心，无法命中 | 确认附加的是游戏子进程，使用 Debug 构建并加载该工程的符号；重新启动游戏后要重新附加新进程 |
| `Output must be a new directory` | 换一个输出目录，或重新生成 `$stamp` |
| `experimental-pending` / `Publication rejected` | 查 staging 中的 `compatibility.json`；修改过的配置需要 `--experimental`，明确不支持的 API 需要调整代码 |
| `AOT assembly mismatch` | AOT 业务库改变后，对该目标使用 `--aot --build --experimental` |
| 模板缓存缺失或版本 / GodotSharp 不匹配 | 用对应目标的 `--build` 重建；完整诊断见 staging 的 `pipeline.log` |
| `Another LeanCLR publication is active` | 等前一个发布进程完成；不要并行启动 |
| Web 无法加载 / 黑屏 | 确认通过 HTTP 访问整个发布目录，查看 F12 Console 和 Network；确认没有误用 `?smoke` |
| Android 启动后立即退出 | 确认安装的是无 `--smoke` 的试玩 APK；用 `adb logcat -s godot` 查看启动错误 |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 通常是签名不同。优先保留原来的本地 debug keystore；确需卸载本 demo 后重装时，注意卸载会删除该应用数据 |

成功目录含 `publication.json`、`compatibility.json`、`artifacts.json`。发布失败时，日志保存在输出目录旁的 `*.staging-*` 文件夹中；没有正式输出目录是正常的失败行为。

进一步说明见 [发布 SDK](publication-sdk.md) 和 [M4 / M5 验收记录](m5-validation.md)。

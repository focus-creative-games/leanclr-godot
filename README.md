# LeanCLR Godot

使用官方 Godot 4.7.2 .NET 编辑器开发和调试 C#，发布后由 upstream LeanCLR `coreclr-minimal` 执行同一份玩法源码。Win64、HTML5 和 Android x64（MuMu）已完成 M0–M5 的本轮验收。

首次体验、官方 .NET 编辑器开发调试及三平台发布步骤见 [Demo 操作说明](docs/demo-guide.zh-CN.md)。统一发布命令、可选编辑器菜单和模板包见 [发布 SDK](docs/publication-sdk.md)，结果与性能边界见 [M4 / M5 验收记录](docs/m5-validation.md)。本轮验证的是明确的样例 API 范围，未宣称完整 Godot / .NET API 或 Android ARM64 支持。

原有 GDExtension 极简 demo 保留用于底层回归；它可直接使用标准 Godot 发布程序。正式 C# Node2D 路线使用专用引擎模板，构建需要固定版本 Godot 源码。

[LeanCLR](https://github.com/focus-creative-games/leanclr) 是一个使用 C++17 实现的轻量级、跨平台 CLR 运行时，面向将 C# 逻辑嵌入游戏、应用和其他原生宿主的场景，支持泛型、异常、反射和委托等核心能力。本项目通过 LeanCLR 的公共宿主接口运行 C# 玩法逻辑，由 Godot 负责输入与呈现。构建、集成及互操作说明见 [LeanCLR 官方文档](https://doc.leanclr.com)。

当前范围是 Windows x64 和单线程 WebAssembly32。它提供运行时宿主与固定缓冲区协议，尚未实现 GodotSharp、C# 脚本挂载、编辑器 Tool 脚本、线程或程序集热重载。

官方 .NET 开发、LeanCLR 发布的 [M0 验证记录](docs/m0-validation.md) 已完成：Windows/Wasm 公共 ABI、嵌套回调与 GC 验证通过，专用 headless 工具已验证 Windows/Web 导出原型。

正式架构采用“官方 Godot .NET 编辑器开发调试，LeanCLR 仅用于发布”。技术方案及阶段门槛见 [Godot .NET 开发与 LeanCLR 发布](docs/dotnet-development-leanclr-publishing.md)。M0 原型标记 `runtime_ready=false`；真实 C# 节点的 LeanCLR 发布 backend 和运行模板已在 M1–M5 验证。

[M1 Windows Node2D](docs/m1-validation.md) 已跑通：同一份 C# 在官方 .NET 编辑器开发，发布 EXE 由 LeanCLR 执行，并验证输入、GC、属性和实际绘制。本轮后续平台验收范围为 Win64、HTML5、Android（MuMu localhost:7555）。

[M2 语义契约](docs/m2-validation.md) 已通过 Windows x64 对比验收，覆盖同步信号、资源、集合、实例化和生命周期，三次独立进程均无退出资源泄漏。

[M3 HTML5](docs/m3-validation.md) 已通过 Chrome/WebGL2 验收，包含 Node2D 真实键盘移动、15 项语义契约与页面刷新重建运行时。

[M4 Android](docs/m4-android-validation.md) 和 [M5](docs/m5-validation.md) 已完成：九组平台／工程验收、三平台混合 AOT、26 项语义／扩展契约、160 MiB GC 压力及发布拒绝检查通过。新增源码配置需显式实验发布并补充测试。

## 依赖

- Godot 4.7.2 标准版，本机默认路径为相邻目录 `v4.7.2-stable_win64`。
- LeanCLR 官方仓库的 Git submodule，默认 `extern/leanclr`，固定在已验证的 `coreclr-minimal` 提交。版本见 `dependencies.json`，可通过 `-RuntimeSource` 指定其他工作树。
- CMake 3.22+、Visual Studio 2022 C++ 工具链、Python、.NET 10 SDK。
- .NET 10.0.8 x64 BCL；Web 使用匹配位宽的 x86 BCL，不能复制 x64 CoreLib。
- Web 使用项目内固定的 Emscripten 4.0.20、Ninja 和 Node。

LeanCLR 通过父仓库的 submodule gitlink 固定提交；`.gitmodules` 中的 `coreclr-minimal` 分支用于显式更新时选择分支，普通 `submodule update` 仍检出固定提交。godot-cpp 来自官方固定提交；依赖准备会验证下载哈希并原子写入目录。没有使用第三方 LeanCLR fork，也没有 CoreLib 布局补丁。

首次克隆时使用：

```powershell
git clone --recurse-submodules https://github.com/focus-creative-games/leanclr-godot.git
```

已有工作目录则在本仓库根目录执行 `git submodule update --init --recursive`。

## 构建和运行

在本仓库根目录的 PowerShell 中执行：

```powershell
python tools/prepare_dependencies.py
./tools/build.ps1 -Target native
../v4.7.2-stable_win64/Godot_v4.7.2-stable_win64_console.exe --path demo
```

默认使用 `extern/leanclr`。需要改用其他 LeanCLR 目录时，可使用相对于本仓库根目录的路径，例如将源码放在相邻的 `leanclr` 目录中：

```powershell
./tools/build.ps1 -Target native -RuntimeSource "../leanclr"
./tools/build.ps1 -Target web -RuntimeSource "../leanclr"
```

直接调用 CMake 时仍可设置 `-DLEANCLR_SOURCE_DIR=<其他目录>`；直接运行托管准备工具时可传 `--runtime-source <其他目录>`。使用外部目录不要求初始化 LeanCLR submodule。CMake 会保留已有缓存中的路径，切换目录时需显式传入覆盖值；`build.ps1` 会在每次构建时传入所选路径。

点击 START FLIGHT 或按空格开始，方向键或 A/D 移动，也支持鼠标／触屏拖动。黄色物体得分，红色物体扣生命。

桌面导出与验证：

```powershell
python tools/fetch_templates.py
./tools/export.ps1 -Target native
./tools/smoke.ps1 -Exported
./tools/smoke.ps1 -Capture
```

导出文件位于 `build/export/native/`，须一同分发 EXE、PCK、原生扩展和 notices。发布包不依赖目标机器安装 .NET runtime。

## Web

先准备 32 位 BCL，已有文件时可跳过下载。在默认 LeanCLR submodule 中执行：

```powershell
Push-Location extern/leanclr
python scripts/dotnet10/fetch-corelib.py
Pop-Location
```

默认产物为该目录下的 `out/net10-runtime-win-x86/runtimes/win-x86/lib/net10.0`。指定 `-RuntimeSource` 时，改在对应工作树执行同一准备命令；构建会从所选源码目录查找 BCL。

随后在本仓库执行：

```powershell
python tools/prepare_web.py
python tools/fetch_templates.py
./tools/build.ps1 -Target web
./tools/export.ps1 -Target web
python tools/serve.py
```

打开 [本地 Web demo](http://127.0.0.1:8060/)。发布文件位于 `build/export/web/`，使用官方单线程、支持 GDExtension 的模板。模板仅下载所需 ZIP 条目并校验原始 ZIP CRC，不需要安装整套导出模板。

不要混用不匹配的 Emscripten 工具链与 Web 模板。仅生成 Wasm 或导出成功不足以证明浏览器已运行。

本机已验证 Windows 与 Chromium WebGL2：两端确定性测试均输出 `ticks=121 x=942 entities=3 remaining=58000`，并正常停止。浏览器也已验证点击开始、方向键移动、计分和生命变化。打开 `http://127.0.0.1:8060/?smoke` 可执行 Web 玩法测试，成功时控制台输出 `LEANCLR_SMOKE_OK`。细节见 `docs/minimal-demo-validation.md`。

## 公共接口与数据协议

`native/` 仅包含 LeanCLR `engine_host.h`、`leanclr.h` 公共头文件，不读取托管数组、GC 或 BCL 内部布局。

1. `leanclr_engine_start` 加载 `Demo.Entry`，调用 `Initialize()`。
2. 用公共程序集／方法查找和 `leanclr_invoke_with_buffer` 调用一次 `AttachBuffersV1(nint,nint,int,int)`。
3. 每帧写入固定输入缓冲区，调用 `leanclr_engine_tick`。C# 在 `Tick(float)` 中计算玩法并写入原生输出缓冲区。
4. Godot 复制经过头部与数量校验的快照，绘制 UI 和实体。
5. 退出时调用 `leanclr_engine_stop`，执行 `Shutdown()` 并清除托管侧的原生地址。

缓冲区在宿主节点内固定存储，覆盖整个会话生命周期。桥接不返回托管对象、不注册原生函数指针回调、不依赖 unmanaged calli。固定数组限制为 64 个实体；快照头部为 16 个 int32，随后每实体三个 int32。此接口针对随包编译的可信 demo 程序集，不是任意 DLL 的通用调用协议。

C# Tick 稳态复用玩法数组；原生帧调用使用固定缓冲区。`get_snapshot()` 为呈现创建一次 PackedInt32Array 副本，因此整条链路并非零分配。

## 生命周期和边界

- 一个游戏进程一个运行时，所有 VM 调用在启动线程执行。场景切换应保留宿主；停止后重新运行游戏进程。
- 编辑器仅注册原生类型，不启动 VM，扩展 `reloadable=false`。
- 帧 delta 限制为 0.1 秒，避免后台恢复时无限追帧；游戏积分步长不超过 16ms。
- 加载器仅允许 demo 和两个受控 BCL 程序集，单文件最多 64 MiB，成功借用的缓冲区由 runtime 复制后释放。
- 桌面使用 NATIVE host，Web 使用分支既有 Wasm 契约的 PORTABLE host；这些选项不会启用线程或补齐全部 System.IO API。
- 当前固定版本 runtime 的 `GetCPInfo` C 符号与 Win32 导入冲突。CMake 仅对对应 runtime 源文件设置名称隔离宏，不修改源码、注册字符串、布局或 ABI。

## 验证

`tools/smoke.ps1` 在独立进程运行 120 帧确定性输入，检查 121 次总 Tick、玩家 x=942、时间递减、生成实体与正常 Shutdown。`-Capture` 使用真实图形驱动并保存 `build/desktop-demo.png`。

准备过两个目标的 BCL 后，运行 `python tools/negative_smoke.py`，可验证缺失 CoreLib、错误位宽 CoreLib 的受控启动失败与缓冲区释放。

构建、验证日志与发布产物保存在 `build/`，不提交二进制。研究与平台验证记录位于 `docs/`。玩法与工具脚本的来源及许可证见 `THIRD_PARTY_NOTICES.md`。

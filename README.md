# LeanCLR Godot

通过 GDExtension 将 upstream LeanCLR `coreclr-minimal` 集成到标准 Godot 4.7.2，运行“C# 玩法＋Godot 呈现”的最小 demo。无需 Godot 引擎源码。

当前范围是 Windows x64 和单线程 WebAssembly32。它提供运行时宿主与固定缓冲区协议，尚未实现 GodotSharp、C# 脚本挂载、编辑器 Tool 脚本、线程或程序集热重载。

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

默认使用 `extern/leanclr`。需要改用其他 LeanCLR 目录时：

```powershell
./tools/build.ps1 -Target native -RuntimeSource "D:/workspace/wasmclr/leanclr-coreclr-minimal"
./tools/build.ps1 -Target web -RuntimeSource "D:/workspace/wasmclr/leanclr-coreclr-minimal"
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

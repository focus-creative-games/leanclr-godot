# M0 验证记录

日期：2026-11-13。状态：**M0 已完成**。M0 验证公共调用边界和导出原型；真实 GodotSharp/C# Node2D 在 LeanCLR 上运行属于 M1。

## 固定版本

- LeanCLR submodule：`b19308a21dae8c58d3ec4fb7e850e24a565d47f1`，来自官方 `coreclr-minimal`。子模块工作树保持干净，没有本地 runtime 补丁。
- Godot：`ed1daf0bf001b61586d9930840f2f1394092c079`，匹配已安装的官方 4.7.2 .NET 编辑器。
- Godot 源码：`extern/godot`。`tools/prepare_godot.py` 校验归档 SHA-256：`e607e9985e1c201bc9cdc1aec8a120f0c3f53b9603f1f828e2b748534a2471ef`。
- Windows x64 / Wasm32 分别使用已锁定的 .NET 10.0.8 x64 / x86 CoreLib。Wasm 工具链为 Emscripten 4.0.20。
- 原有 `-RuntimeSource` / `LEANCLR_SOURCE_DIR` 源码覆盖方式保留。

## 退出条件与结果

| M0 门槛 | 结果 |
| --- | --- |
| Godot 和 LeanCLR 源码锁定 | 已完成；Godot 发布工具补丁单独保存 |
| Windows / Wasm 公共 ABI 正负用例 | 全部通过；Wasm 实际在 Node 执行 |
| 同步嵌套、GC、异常恢复 | 全部通过；包括五层嵌套和外层双引用结构体存活 |
| Windows / Web headless 导出原型 | 已生成实际平台产物，并挂载其 PCK 验证脚本映射与 payload |
| 导出错误拒绝 | 哈希损坏、目标不匹配、缺少显式 staging 均拒绝 |
| 开发源码与官方编辑器保持原样 | 受保护文件导出前后哈希一致 |

## 开发侧基线

```powershell
./tools/m0-dotnet.ps1
```

脚本使用用户提供的官方 .NET 编辑器及其本地 NuGet SDK，针对同一 `samples/dotnet` 工程两次构建并启动独立游戏进程。验证了 `[Export]` 属性、`_Process`、Position 更新、新 DLL 加载及静态状态重置：

```text
M0_DOTNET_OK revision=1 instances=1 x=8
M0_DOTNET_OK revision=2 instances=1 x=8
M0_DOTNET_REPLAY_OK
```

交互式 IDE 断点和手工点击 Stop/Play 不在该自动化测试范围。开发样例使用官方 SDK 的 net8.0；发布到 LeanCLR 的 BCL/GodotSharp 适配仍属于后续阶段。

## 公共 ABI、GC 与异常

```powershell
./tools/m0-abi.ps1 -Target native
./tools/m0-abi.ps1 -Target web
```

宿主探针只包含 `public/engine_host.h`、`public/leanclr.h` 对应的公共头文件，不访问对象布局或 VM 私有结构。注册发生在启动、解析目标方法之前，避免缓存未实现的入口。

Windows x64 与 Wasm32 都通过：

- 引擎启动、终态停止、程序集缓冲区取得/释放配对。
- 标量和顺序 blittable 结构体传参、返回值及槽位布局。
- 托管异常输出，以及后续成功调用清除旧异常输出。
- 空 method、空参数缓冲区、空返回缓冲区被拒绝；可省略异常输出。
- 托管 → C invoker → 托管的同步嵌套，回调执行 `GC.Collect()` 后正确返回外层。
- 连续五层同步回调，验证各层返回状态恢复。
- 内层异常被原生观察后，继续调用正常托管方法，异常状态不污染外层。
- 托管异常经 C invoker 返回托管 `catch (DivideByZeroException)`。
- 64 次重复 GC/回调，检查外层含两个引用的结构体中两个数组仍然存活；Wasm32 上两个引用位于同一八字节槽位。

关键日志：

```text
M0_ABI_PASS synchronous-native-managed-GC-nesting
M0_ABI_PASS five-level-synchronous-nesting
M0_ABI_PASS inner-exception-recovery
M0_ABI_PASS native-exception-propagation
M0_ABI_PASS repeated-GC-root-survival
M0_ABI_PASS assembly-buffer-ownership
```

上游已修复五参数 C invoker 与内部 `RtResultVoid` invoker 的类型适配，以及异常输出清除。本集成验证真实托管 P/Invoke 路径；其余注册种类由上游 public-invoker 测试覆盖，本报告不将上游测试冒充为本仓库执行结果。这里也没有进行调用性能和分配预算验收。

## 独立 headless 发布工具

```powershell
python tools/prepare_godot.py
./tools/build-m0-exporter.ps1
python tools/m0-export.py
```

构建工具需要 MSVC、.NET SDK 和首次 NuGet 恢复网络；SCons 4.8.1 安装在项目 `.tools` 中。工具输出在 `extern/godot/bin`，使用 `._sc_` 便携模式隔离编辑器设置。其渲染/物理模块配置面向 headless 资源导出，不用于日常开发或作为游戏运行模板。

官方 .NET 编辑器的 Web 导出存在两个阻断点：

1. `platform/web/export/export_plugin.cpp` 的原生校验在启用 mono 模块时直接拒绝 Web。
2. `GodotTools/Export/ExportPlugin.cs` 的官方托管发布流程排除 Web，并负责 C# 资源占位处理。

`godot_patches/m0/export-policy.patch` 只接管这两个导出策略点；新增 `LeanClrM0Export.cs` 验证显式 staging 中的目标、版本和文件哈希，注入 `.leanclr` payload 后跳过官方 dotnet publish，继续复用官方 C# 占位文件、场景转换、UID 缓存与平台打包。没有使用旧 fork 的内存布局补丁。

补丁基线/结果文件哈希保存在 `source-hashes.json`；准备脚本拒绝覆盖未知源码修改。没有 staging 时保留原生 Web 拒绝行为。导出工具检查成功标记和实际产物，避免将托管插件捕获错误后的零退出码当作成功。

原型将工程复制到 `build/m0/export/<target>/project`，原工程和安装的官方编辑器不被改写。它导出 Windows EXE/PCK 和 Web HTML/JS/Wasm/PCK，随后在独立进程中挂载 PCK，验证：

- payload 各文件 SHA-256 以及对应平台 CoreLib；
- `res://Player.cs` 为换行占位文件；
- 导出的场景可恢复为 PackedScene，引用路径仍为 `res://Player.cs`，脚本类型为 CSharpScript，导出属性值为 120；
- `scripts.json` 保留程序集、类型、基类和源脚本 UID 映射。

```text
M0_EXPORT_OK native
M0_EXPORT_OK wasm
M0_EXPORT_ALL_OK development sources and installed editor unchanged
```

**原型的 manifest 明确标记 `runtime_ready=false`。** 场景映射验证借助私有工具中的官方 .NET 后端和 staging 的开发 DLL；不是 LeanCLR 上的脚本执行验证。payload 中 GodotSharp 仍是官方开发 DLL，尚未做发布适配，也尚未进行完整依赖闭包扫描。生成的 `probe.exe` / `probe.html` 不是可交付的 LeanCLR C# 游戏。

实际产物、验证报告和日志分别位于：

- `build/m0/export/native/artifacts/`
- `build/m0/export/wasm/artifacts/`
- `build/m0/export/validation.json`
- `build/m0/abi-native.log`、`build/m0/abi-web.log`

早期 `tools/m0-pack.py` 仍保留为 PCK 容器探针；M0 的导出验收已使用真正的平台导出流程，不再以单独的 PCKPacker 实验代替。

## M1 交接

下一阶段实现发布用 GodotSharp 适配、LeanCLR 脚本 backend 和 Windows 模板，让同一个真实 C# Node2D 在官方编辑器开发、在 LeanCLR 发布进程运行。M0 已证明公共调用和导出接管可行，不代表完整 Godot C# API 已兼容。

公共 ABI 回归现使用独立的 `tests/m0/CMakeLists.txt`，native/Web 构建目录分别为 `build/m0/probe-native` 与 `build/m0/probe-web`，不再依赖原 GDExtension 工程。

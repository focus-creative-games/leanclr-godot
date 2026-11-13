# 最小集成验证记录

日期：2026 年 11 月 13 日。

## 实现范围

Windows x64 与 WebAssembly32 共用一个 Godot GDExtension 宿主和一份 C# 玩法源码。输入、逻辑和呈现之间以固定原生缓冲区交换数据。未使用 GodotSharp、运行时私有头文件、托管数组布局或旧 fork 布局补丁。

生命周期使用公共 `engine_host.h`；一次性的缓冲区连接使用 `leanclr.h`。启动后只通过 `leanclr_engine_tick` 执行托管玩法。Runtime 源码未修改；Windows 构建对当前版本的 GetCPInfo C 符号设置文件级名称隔离宏，避免与 Kernel32 导入冲突。

## 版本

| 组件 | 本次版本 |
| --- | --- |
| Godot 发布程序与官方导出模板 | 4.7.2 stable，ed1daf0bf |
| LeanCLR | coreclr-minimal，7d9a431eb1313f9f61bc1b3b1bdfcdc5ea95ce48 |
| godot-cpp | 507ed9d840c01a3c5b2a39af8bb4000bfac30bf5，4.7 API |
| BCL | .NET 10.0.8；Windows 用 x64，Wasm 用 x86 CoreLib |
| Windows 编译器 | MSVC 19.44，Visual Studio 2022 |
| Web 编译器 | 项目内固定 Emscripten 4.0.20 |
| 桌面图形 | NVIDIA RTX 4060，OpenGL 3.3 Compatibility |
| Web 图形 | Codex in-app Chromium，WebGL2 Compatibility |

CoreLib、godot-cpp 和工具链下载哈希见仓库根目录 `dependencies.json`。各目标的托管文件哈希保存在生成的 `demo/managed/<target>/provenance.json`。

## 通过的检查

| 检查 | 结果与证据 |
| --- | --- |
| 文档化 Windows 构建脚本 | `tools/build.ps1 -Target native` 通过 |
| 源工程 headless 玩法 | Initialize、Attach、120 帧输入与 Shutdown；通过 |
| Windows EXE 导出包 | 独立 EXE 运行相同测试，退出码 0 |
| 桌面真实渲染 | NVIDIA OpenGL 执行相同测试并保存截图；通过 |
| 缺失 CoreLib | 受控启动失败，退出码 1，缓冲区 0/0 |
| 错误位宽 CoreLib | 明确报告 pointer size 4 与 8 不匹配，退出码 1，缓冲区 1/1 |
| 文档化 Web 构建与导出 | 官方单线程 GDExtension 模板；通过 |
| 真实浏览器 C# 玩法 | `?smoke` 模式结果与桌面一致，正常 Shutdown，缓冲区 2/2 |
| 浏览器手动输入链路 | 点击 START FLIGHT、右方向键移动；画面显示实体、积分与生命变化 |
| C++ 格式 | 使用 LeanCLR 仓库 clang-format.exe 与 .clang-format 格式化，dry-run 通过 |
| Python 工具 | 语法编译通过 |

两端相同的玩法日志：

```text
LEANCLR_READY buffers_v1 files=2/2
LEANCLR_SMOKE_OK ticks=121 x=942 entities=3 remaining=58000
LEANCLR_STOPPED files=2/2
```

121 包含初始化后的零 delta 快照 Tick，加上测试的 120 帧。测试使用固定输入和随机种子，不依赖实际机器帧率。

## Web 注册问题

首次浏览器执行在 GDExtension 类注册期间出现函数签名不匹配，当时尚未进入 LeanCLR VM。将工具链从本机旧版本对齐到 4.0.20 后，该错误仍然存在；将宿主实现设为 hidden visibility 并隐藏 inline 符号后，浏览器正常启动。最终 CMake 配置保留此设置，并只显式导出扩展入口。

该修复没有启用函数指针强制转换模拟，没有绕过 Wasm 类型检查，也没有修改 CoreLib 或 MethodTable 布局。

## 产物与复现

- Windows：`build/export/native/leanclr-demo.exe`、PCK、扩展库与 notices。
- Web：`build/export/web/`，运行 `python tools/serve.py` 后访问 `http://127.0.0.1:8060/`。
- 桌面截图：`build/desktop-demo.png`。
- 浏览器截图：`build/web-demo.jpg`。
- 桌面日志：`build/exported-final-smoke.log`、`build/rendered-final-smoke.log`。
- 失败路径日志：`build/missing-corelib.log`、`build/foreign-corelib.log`。
- 浏览器日志：`build/browser-gameplay-logs.json`。

生成文件均在忽略目录内，复现命令见 README。发布 EXE 已在本机以独立导出程序运行；尚未在完全未安装 .NET 的干净系统上验收。当前宿主由自身加载随包 BCL，不使用 hostfxr 或系统 CoreCLR。

这次验证不代表其他浏览器、移动设备、触屏、Linux/macOS、AOT、长时间压力、完整 BCL 或 Godot C# 脚本兼容已经通过。

## LeanCLR submodule 默认路径验证

LeanCLR 源码改为官方仓库的 `extern/leanclr` Git submodule，gitlink 固定在上述同一提交。已通过默认路径的 Windows 构建与玩法 smoke，以及 Web 构建和导出。日志分别保存在 `build/submodule-native-build.log`、`build/submodule-native-smoke.log`、`build/submodule-web-build.log` 和 `build/submodule-web-export.log`。

另外以全新 CMake 缓存分别验证了默认 submodule 路径与显式 `LEANCLR_SOURCE_DIR` 外部工作树；托管准备工具的 `--runtime-source` 外部目录覆盖也已通过。此次仅调整依赖引用与默认路径，没有修改运行时或宿主 C++ 实现。

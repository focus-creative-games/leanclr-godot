# M4 / M5 验收记录

日期：2026-11-14。按本轮约定，验收范围为 Win64、HTML5 和 Android x64（MuMu `localhost:7555`）。M0–M5 已在这个范围内完成；这不代表全套 Godot / .NET API 或其他 Android 架构已经支持。

## M4 发布工具

统一入口为 `tools/publish.py`，支持解释模板和混合 AOT 模板，开发工程不作为导出工作目录。每次发布使用独立 staging，验证成功才产生正式输出目录，失败保留日志。完整使用方法见 [发布 SDK](publication-sdk.md)。

- Win64 / HTML5 / Android × Node2D / 15 项语义 / 11 项扩展契约，共九组通过。记录在 `build/ci/28888355/report.json` 及各输出目录。
- 官方 .NET 编辑器已验证可加载可选发布菜单；Play、DLL 重编译和调试继续使用官方后端。两次修改版本的 DLL 在新 Play 进程中加载验证通过；未自动化验证 IDE 断点。
- 9 项负向检查通过：不支持的 Thread、未知工程、显式 experimental 标记，以及错误位宽、runtime 版本、CoreLib、GodotSharp、损坏的 Gameplay DLL、AOT DLL 不匹配。记录在 `build/sdk/guards/report.json`。
- 模板、程序集、源文件及发布产物均有 SHA-256 清单；宿主在创建脚本前拒绝不兼容组合，每个加载的 DLL 都验证内容哈希。
- 提供经过解包哈希复核的三平台模板 ZIP，以及使用已准备 Windows runner 的手动 CI 工作流。CI 命令链在本机执行通过，未向远程 runner 提交运行。

Android 的 15 项语义、嵌套调用 / GC / 异常、前后台恢复、进程重建和实际绘制见 [Android 记录](m4-android-validation.md)。官方 LeanCLR submodule 保持干净。初次验收使用的 Android 临时修复现已由上游 `7d98994` 接收，本地补丁、源码副本构建流程和 zlib 宏覆盖已移除；更新后的验证见 [上游修复记录](upstream-android-validation.md)。

## M5 混合 AOT 与正确性

`managed/DemoLogic/Motion.cs` 仍是两种后端共享的业务源码。LeanAOT 编译 `Step` 和 `Benchmark`；Gameplay、GodotSharp、bootstrap、BCL 及其余方法继续解释执行。没有在业务代码中加入 `#if LEANCLR`。

三平台均观察到来自已编译 `Step` 函数的 `LEANCLR_AOT_HOTCALL ... step=4`，并得到相同四帧结果 `instances=1, x=8, speed=120`。Chrome 验证三次页面实例，MuMu 验证三个独立进程。Android 的证明在热点第四次调用时输出，不依赖进程析构日志。

Windows 额外比较了 200,000 次整数循环及 100 次非精确浮点累积：整数结果均为 `1834275088`，浮点位模式均为 `-1079759472`。AOT 使用 `/fp:precise` 或 `-ffp-contract=off`；没有用隐式浮点收缩换取速度。报告记录 AOT DLL 的精确哈希，替换它必须重新生成和编译模板。

记录：`build/m5/performance/report.json`、`build/m5/web-final/`、`build/m5/android-final/`。Win64 发布进程再次检查未加载 CoreCLR、hostfxr、hostpolicy 或 CLR DLL。

## 性能预算

本节数值为原始 M5 基线的测量记录；后续 runtime 更新的功能回归结果单独记录，不将旧测量冒充新版本性能数据。

本机各后端 7 个新进程计算样本，另有 3 次、每次 232 个预热后的 C# 帧工作样本。下表帧 P95、GC 和工作集列取三次中的最大值。

| 后端 | 计算中位耗时 | C# 帧工作 P95 | GC 暂停 | 热帧托管分配 | 进程峰值工作集 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 官方 .NET | 0.236 ms | 0.014 ms | 0.717 ms | 0 B/帧 | 127.48 MiB |
| LeanCLR 解释 | 4.287 ms | 0.033 ms | 0.547 ms | 0 B/帧 | 114.20 MiB |
| LeanCLR 混合 AOT | 0.236 ms | 0.036 ms | 0.659 ms | 0 B/帧 | 113.90 MiB |

通过的回归预算：AOT 计算加速至少 2 倍，计算最长耗时 20 ms；解释计算最长耗时 2 s；C# 帧工作 P95 小于 2 ms，GC 小于 20 ms，每帧托管分配小于 64 B，LeanCLR 进程峰值工作集小于 256 MiB。

实际计算加速约 **18.17 倍**。这不表示游戏帧率提高 18 倍：这里的短帧工作主要经过引擎边界，未观察到同等幅度的整帧收益。GPU 绘制不在计时区间；引擎模板保留便于迭代的构建配置，进程内存比较也包含引擎构建差异。以上是样例回归预算，不是大型游戏的性能承诺。

原先每帧传入字符串动作名会创建临时 `StringName`，还会触发跟踪容器扩容。样例改为缓存动作名后，三后端均测得零托管分配。宿主的反向调用仍使用栈槽和缓存入口，不逐帧反射或创建 `object[]`。

## 裁剪、扩展 API 与内存

发布按 bootstrap、Gameplay、GodotSharp 和 DemoLogic 的引用闭包选取程序集。当前闭包 40 个程序集、31,715,080 字节，其中所需 BCL 为 25,763,592 字节；已安装托管 BCL DLL 总量为 63,080,856 字节（172 个，排除 native DLL）。没有复制整个共享运行时目录，也没有携带 CoreCLR。所有保留程序集的 IL 和元数据完整保留，不做缺少反射根证明的成员裁剪。SDK 私有构建去掉无用 PDB 和与 Git 提交号相关的程序集版本后缀，避免提交日志变化导致模板指纹失配。

在 M2 的 15 项语义上新增并逐平台验证 11 项：Unicode StringName、NodePath 包装身份、场景组、原生变换、JSON / Variant、Unicode 文件、字节数组、Tween、延迟调用、QueueFree 和大堆 GC 存活。

大堆样例保留 5 × 32 MiB 数组，GC 后逐一验证首尾数据。Chrome 三次运行均将线性内存从初始 128 MiB 增长到 **265.5 MiB**，低于 384 MiB 的该样例预算。Windows、Chrome、MuMu 的契约结果与官方 .NET 相同。此测试不代表任意对象图的 GC 暂停都相同。

## 当前产物与重现

- Windows：`build/export/m5/aot-v3/leanclr-node2d.exe`，不带参数运行可试玩。
- HTML5：`build/export/m5/web-v3/`，通过 HTTP 服务打开 `index.html`；正常页面已用真实方向键验证移动。
- Android：`build/export/m5/android-playable/demo.apk`，无自动退出参数；已在 MuMu 安装并验证可见绘制、前后台恢复和进程重建。
- 模板包：`build/sdk/dist/leanclr-godot-4.7.2-{interpreter,mixed}.zip`。

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --output build/release/win --aot --build
python tools/publish.py --target html5 --sample samples/dotnet --output build/release/web --aot --build
python tools/publish.py --target android --sample samples/dotnet --output build/release/android --aot --build
```

当前 SDK 默认仅接受已执行过的精确样例源码配置；其他工程必须显式使用实验模式并补充执行测试。多线程、动态代码、用户本地库加载、Web Stopwatch、完整 BCL、全部 Godot 模块、ARM64 / 真机 / 商店签名仍不能由本次结果推导为可用。

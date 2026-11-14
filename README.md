# LeanCLR Godot

LeanCLR Godot 为 Godot C# 项目提供基于 LeanCLR `coreclr-minimal` 的发布运行时。开发和调试使用官方 Godot 4.7.2 .NET 编辑器，发布后的游戏由 LeanCLR 执行同一份玩法源码，支持解释执行和混合 AOT。

集成复用 Godot 的 CSharpLanguage、CSharpScript 和 GodotSharp，业务代码直接使用 Godot 对象与 API。编辑器中的 Play、脚本重载和 C# 调试仍使用官方 .NET 后端；LeanCLR 运行在发布后的游戏进程中。

## 平台支持

| 发布目标 | 当前支持范围 | 限制 |
| --- | --- | --- |
| Windows | Windows x64 | 使用专用 LeanCLR 发布模板 |
| HTML5 | 浏览器 WebAssembly | 通过 HTTP 服务运行，使用单线程宿主 |
| Android | MuMu 模拟器原生 x86_64 | 当前提供调试 APK；ARM64、真机、AAB 和商店签名尚未验证 |

当前提供 Windows 开发机上的构建与发布工具链。上述平台的验证范围限于仓库内样例，不代表任意 Godot C# 项目或全部 Godot / .NET API 均已兼容。

## 开始使用

### 获取源码与依赖

```powershell
git clone --recurse-submodules https://github.com/focus-creative-games/leanclr-godot.git
cd leanclr-godot
# 已有工作目录中初始化或更新依赖：
git submodule update --init --recursive
```

LeanCLR 以 Git submodule 引入，默认路径为 `extern/leanclr`，依赖版本见 `dependencies.json`。普通 submodule update 使用仓库固定的提交，不自动追踪分支最新版本。

发布需要固定版本的 Godot 源码、私有 headless 导出器、官方 .NET 编辑器、.NET SDK 10 和匹配的 BCL，以及目标平台的工具链。Windows 使用 MSVC 2022、CMake、Python 和 SCons；Web 还需要 Emscripten，Android 还需要 Android SDK / JDK。完整版本和准备条件见 [发布 SDK](docs/publication-sdk.md)，Emscripten 准备入口为 `python tools/prepare_emsdk.py`。

### 开发与调试

1. 用官方 Godot 4.7.2 .NET 编辑器导入 `samples/dotnet/project.godot`。
2. 完成 C# 构建和资源导入后，按 F5 运行。样例中可用左右方向键移动蓝色圆点。
3. 使用 Visual Studio 等 C# IDE 附加到游戏子进程进行托管调试。
4. 修改 C#、场景或资源后，先在官方编辑器中重新构建、导入并验证，再发布 LeanCLR 版本。

开发工程保留现有 `net8.0` 配置；发布工具会独立构建所需程序集。详细操作见 [Demo 操作说明](docs/demo-guide.zh-CN.md)。

### 发布

在仓库根目录执行以下命令。首次发布使用 `--build` 构建对应模板，输出目录必须位于仓库内、不能位于 samples 内，且不能已经存在。各目标应依次发布。

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --build --output build/release/windows
python tools/publish.py --target html5 --sample samples/dotnet --aot --build --output build/release/web
python tools/publish.py --target android --sample samples/dotnet --aot --build --output build/release/android
```

- 去掉 `--aot` 使用纯解释模板。当前混合 AOT 仅编译 DemoLogic 的两个方法，其余代码继续解释执行，保留完整 IL 和元数据。
- 后续可省略 `--build` 复用匹配的模板；修改编译进模板的 AOT 业务代码后，需要重新构建模板。
- SDK 默认只接受已验证的精确样例配置。修改源码、场景或资源后，需要加 `--experimental` 并自行补充测试；该选项仍会拒绝已知不支持的依赖。
- Windows 运行时需保留完整发布目录；Web 需通过 HTTP 服务访问发布目录；Android 当前产物安装到 MuMu x64 运行。

可选的官方编辑器发布菜单安装方式：

```powershell
python tools/install-editor-addon.py samples/dotnet
```

安装后可在“项目 → 工具”中使用 `LeanCLR: Publish ...`。菜单使用解释模板；需要 AOT、重建模板或实验模式时使用命令行。LeanCLR 发布使用独立工具链，入口为上述命令或插件菜单。

## 兼容范围与限制

- **脚本类型**：场景可实例化的 C# 脚本目前要求顶层、非泛型的 public 类型和 public 无参构造；支持脚本继承和抽象基类。这是当前脚本工厂适配器的限制，普通业务代码仍可使用泛型。
- **线程与动态能力**：发布宿主为单线程，所有 VM 调用在启动线程执行。发布检查阻止已知的 Thread、ThreadPool、Task.Run、动态代码生成、用户 P/Invoke 和本地库加载等依赖。
- **API 覆盖**：GodotSharp 复用官方 API 表面，但完整 Godot / .NET API 尚未全部实现或验证。HTML5 下不支持 `Stopwatch` 初始化，可使用 `Godot.Time.GetTicksUsec`。
- **项目适配**：当前源码适配器面向仓库内样例的脚本布局和依赖。其他项目布局、依赖、构造方式或动态注册方式可能需要增加适配及运行验证。
- **发布检查**：静态兼容性扫描无法证明所有反射、间接调用或 BCL 行为均可用。`--experimental` 允许发布待验证配置，不会自动提供 API 兼容性。
- **发布包调试**：当前通过日志、确定性测试和发布报告诊断 LeanCLR 发布包；CoreCLR 托管断点调试用于官方 .NET 开发进程。

发布宿主的额外限制适用于 LeanCLR 发布流程，官方 .NET 编辑器继续提供其正常的开发能力。

## 样例与文档

| 路径 | 用途 |
| --- | --- |
| `samples/dotnet` | 主要试玩与 C# 开发示例 |
| `samples/semantics` | 对象、信号、资源、集合等语义示例 |
| `samples/extended` | 扩展 API 与 GC 压力验证示例 |

- [Demo 操作说明](docs/demo-guide.zh-CN.md)：编辑器开发、C# 调试、三平台发布与运行、常见问题。
- [发布 SDK](docs/publication-sdk.md)：依赖准备、命令选项、兼容性检查、发布报告与 CI。
- [技术方案](docs/dotnet-development-leanclr-publishing.md)：集成架构与设计说明。
- [第三方许可](THIRD_PARTY_NOTICES.md)。

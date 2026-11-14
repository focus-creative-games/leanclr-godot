# LeanCLR Godot

使用官方 Godot 4.7.2 .NET 编辑器开发和调试 C#，发布后由 LeanCLR `coreclr-minimal` 执行同一份玩法源码。当前主线只维护 CSharpScript / GodotSharp 集成与专用发布模板，已完成 Win64、HTML5 和 Android x64（MuMu）的本轮 M0–M5 验收。

## 开始使用

- [Demo 操作说明](docs/demo-guide.zh-CN.md)：现成产物、官方 .NET 编辑器开发调试、三平台发布和运行。
- [发布 SDK](docs/publication-sdk.md)：发布命令、兼容性门槛、编辑器菜单与 CI。
- [技术方案](docs/dotnet-development-leanclr-publishing.md)：架构和实施阶段。
- [M4 / M5 验收记录](docs/m5-validation.md)：实际 API 范围、AOT、性能、GC、产物与已知限制。

主要试玩工程是 `samples/dotnet/project.godot`；`samples/semantics` 和 `samples/extended` 分别验证 15 项语义与 11 项扩展契约。官方编辑器的 Play 和 C# 调试继续使用 .NET，LeanCLR 只进入发布后的游戏进程。

## 当前集成方式

发布后端复用 Godot 的 CSharpLanguage、CSharpScript 和脚本实例体系。GodotSharp 通过函数表和 unmanaged calli 调用 Godot，生成的原生桩反向调用 C#；业务代码按 Node2D、Resource、信号等已验证的 API 编写。

宿主使用 LeanCLR 公共接口，不读取其托管对象、GC 或 BCL 的私有布局。混合 AOT 模式目前编译 DemoLogic 的两个方法，其他代码继续解释执行；完整 IL 和元数据保留。业务直接使用 Godot 对象和 API，无需额外编写实体快照协议。

## 开发与发布约束

- 场景可实例化的 C# 脚本目前要求顶层、非泛型的 public 类型和 public 无参构造；允许脚本继承和抽象基类。这是当前脚本工厂适配器的范围，不是禁止普通业务代码使用泛型。
- 发布运行时为单线程宿主，所有 VM 调用在启动线程执行；发布检查阻止已知的 Thread、ThreadPool、Task.Run、动态代码生成和用户本地库加载等依赖。
- GodotSharp 复用官方 API 表面，不表示完整 Godot / .NET API 均已实现或验证。官方 .NET 编辑器的正常开发能力不受发布宿主额外约束。
- SDK 默认接受已验证的精确样例源码配置。修改源码、场景或资源后需要 `--experimental` 并补充测试；该选项不会使不支持的 API 自动兼容。
- 当前源码适配器面向仓库内样例的脚本布局和依赖。其他项目布局、依赖与动态注册方式可能需要增加适配。
- 当前 Android 验收范围为 MuMu 原生 x64；ARM64、真机、AAB 与商店签名不在本轮验收范围。

## 依赖与发布

LeanCLR 使用官方 Git submodule，默认路径 `extern/leanclr`，固定提交见 `dependencies.json`。普通 submodule update 检出 gitlink 固定提交，不自动追踪分支最新版本。

```powershell
git clone --recurse-submodules https://github.com/focus-creative-games/leanclr-godot.git
# 已有工作目录：
git submodule update --init --recursive
```

发布工具链需要固定版本 Godot 源码、私有 headless 导出器、官方 .NET 编辑器、.NET SDK / 匹配 BCL，以及各目标工具链。当前机器已准备好模板；完整操作和准备条件见上述文档。Emscripten 准备入口为 `python tools/prepare_emsdk.py`。

先使用官方编辑器构建并导入样例，再从仓库根目录发布到一个尚不存在的目录：

```powershell
python tools/publish.py --target win64 --sample samples/dotnet --aot --output build/release/windows
python tools/publish.py --target html5 --sample samples/dotnet --aot --output build/release/web
python tools/publish.py --target android --sample samples/dotnet --aot --output build/release/android
```

去掉 `--aot` 使用解释模板。模板缺失或需要更新编译进模板的业务代码时加 `--build`；修改样例配置后加 `--experimental`。构建脚本保留 `-RuntimeSource`，发布命令保留 `--runtime-source` 外部源码目录选项，发布 SDK 仍校验已验证的 runtime 版本。

## 验证

[M0](docs/m0-validation.md)、[M1](docs/m1-validation.md)、[M2](docs/m2-validation.md)、[M3](docs/m3-validation.md)、[Android](docs/m4-android-validation.md) 和 [M5](docs/m5-validation.md) 记录阶段性验收。当前验证包含九组平台／工程组合、26 项语义／扩展契约、三平台混合 AOT、160 MiB GC 压力和发布拒绝检查。

公共 ABI 回归使用独立的 `tests/m0/CMakeLists.txt`，不依赖 Godot 扩展或脚本绑定：

```powershell
./tools/m0-abi.ps1 -Target native
./tools/m0-abi.ps1 -Target web
```

三平台 SDK 测试入口为 `tools/validate-sdk.ps1`。生成文件与日志保存在 `build/`，不提交二进制；第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## GDExtension 实现归档

GDExtension 集成已从主线移除，单独保存在本地分支 `codex/gdextension-integration`，起点是最早包含该实现的提交 `84f5d91`（`Add minimal LeanCLR integration for Godot desktop and Web`）。该分支包含独立实现、样例、数据协议、构建脚本和当时的说明；不再与当前主线的发布方案混用。

# M3 HTML5 验证

日期：2026-11-14。状态：已完成。

HTML5 使用同一套 Godot CSharpScript 后端和适配 GodotSharp，LeanCLR 直接链接进 Godot 主 Wasm；不使用 GDExtension 侧模块。工具链固定 Emscripten 4.0.20，wasm32、单线程、目标位宽 CoreLib。

## 构建与运行

```powershell
# 先构建目标样例的发布程序集，例如 M2 契约工程：
./tools/build-m1.ps1 -Sample samples/semantics
./tools/build-web-runtime.ps1
python tools/publish-m1.py --sample samples/semantics --target web --output build/export/m3/semantics
python tools/test-web-runtime.py --directory build/export/m3/semantics

# Node2D 可视样例：
python tools/prepare_m1_managed.py --sample samples/dotnet
python tools/publish-m1.py --target web
python tools/test-web-runtime.py --directory build/export/m3/web --expected "NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120"
python tools/test-web-runtime.py --directory build/export/m3/web --movement
```

浏览器测试使用项目 `.tools/browser` 内的 Playwright 1.56.0 和 Pillow 11.3.0，以及本机 Chrome。首次需要将这两个版本安装到该目录；测试自带本地 HTTP 服务。

## 实测

Chrome 157 / WebGL2：

- Node2D 属性、帧更新、输入和绘制结果与 Windows、官方 .NET 一致：`instances=1 frames=4 x=8 speed=120 draws=4`。
- M2 的全部 15 项语义契约通过，包括同步信号、资源保存/回读、GC、删除后访问及重复生命周期。
- 两个样例各完成首次加载加两次同页刷新，均得到新的正确运行时状态。
- 普通可视模式下发送真实 ArrowRight 键盘事件，蓝色圆形横向中心从约 99.50 移动到 220.56 像素，C# 输入和 Position 更新确实驱动 WebGL 呈现。
- 测试没有 JavaScript pageerror。

```text
WEB_RUNTIME_OK M2_SEMANTICS_OK checks=15 observed=31
WEB_RUNTIME_OK NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120
WEB_MOVEMENT_OK from=99.50 to=220.56
```

证据：`build/m3/validation-semantics.json`、`validation-node2d.json`、`validation-movement.json`，包含浏览器版本、重载次数和实际 JS/Wasm/PCK 哈希。移动截图保存在同目录。

## 平台适配

- LeanCLR 模板编译时排除官方 hostfxr/CoreCLR 装载代码，官方 .NET 编辑器仍保留原实现。
- 仅在明确选择 LeanCLR 后端时允许 mono 脚本模块参与 Web 构建。
- 发布器按目标选择 x86 CoreLib 和 BCL 依赖闭包，拒绝错误位宽 CoreLib。
- 初始 Wasm 内存 128 MiB，允许工具链默认的后续内存增长；此处不是内存优化预算结论。
- 页面 `?smoke` 使用 Dummy 音频驱动。极短测试退出曾触发上游音频异步初始化/关闭竞态，因此自动语义测试显式使用无音频配置；普通移动样例不使用该开关。音频 API 兼容性不属于本阶段已验收范围。

M3 没有声称完整 Godot API 或线程支持；这些平台的发布能力仍按已验证契约限定。

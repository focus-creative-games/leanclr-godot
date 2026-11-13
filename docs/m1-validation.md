# M1 Windows Node2D 验证

状态：已完成。平台：Windows x64。

同一份 `samples/dotnet/Player.cs`、场景和导出属性在官方 Godot 4.7.2 .NET 编辑器下构建运行；发布时独立重编译为 net10.0，引用适配后的 GodotSharp，由定制 Windows 模板中的 LeanCLR 执行。没有改写业务代码，没有 GDScript 玩法转发，也没有加载 CoreCLR。

## 复现

先按 M0 准备依赖和私有发布工具，然后执行：

```powershell
./tools/m0-dotnet.ps1
./tools/build-m1.ps1
python tools/publish-m1.py
./tools/smoke-m1.ps1
./tools/smoke-m1.ps1 -Visible
```

运行入口：`build/export/m1/windows/leanclr-node2d.exe`。普通运行可用左右方向键移动蓝色圆形。输出目录附带许可证、程序集依赖清单和发布来源记录。

## 实测结果

- 官方 .NET 两次重新构建/启动分别加载 revision 1、2，每次实例计数为 1。
- 发布 EXE 的 headless 和实际 NVIDIA OpenGL 窗口均通过。
- Godot 原生场景系统加载真实 `CSharpScript`，以现有 Node2D 原生对象构造 C# 实例。
- `[Export] Speed` 场景值 120、`_Ready`、`_Process`、Input.ActionPress/GetAxis/ActionRelease、Position 和 `_Draw` 工作一致。
- 脚本在帧调用中主动 GC，实例绑定与后续调用仍有效。
- 四帧后 Position.X 为 8，构造/Ready 实例数为 1，C# 绘制回调次数为 4，退出码为 0。
- 发布进程整个测试期间采样到的模块中没有 coreclr.dll、hostfxr.dll、hostpolicy.dll 或 clr.dll。

```text
LEANCLR_GODOT_READY backend=LeanCLR script_language=CSharpScript
NODE2D_SMOKE_OK instances=1 frames=4 x=8 speed=120 draws=4
M1_SMOKE_OK mode=visible no_coreclr=true
```

日志与模块采样结果位于 `build/m1/`。交互式 IDE 断点未自动化验证；日常编辑器、标准调试 DLL/PDB 及其构建路径保持官方工作流。

## 实现

- 保留官方 CSharpLanguage/CSharpScript/CSharpInstance、场景资源转换、属性设置和通知派发。
- 发布 GodotSharp 保留完整官方 API 源码与 NativeFuncs 函数表。对返回构造函数地址的签名使用 IntPtr 表示地址，再在调用端转换为对应函数指针，避开嵌套函数指针元数据限制。
- 官方 NativeFuncs 签名加构造/属性回调组成有界 calli 输入：240 个调用点生成成功，去重后 91 个桥。没有将 NativeFuncs 全部改成具名 P/Invoke。
- 37 个 ManagedCallbacks 使用带准确原生签名的 C++ trampoline，经过公共 leanclr C API 调用缓存的托管方法；宿主不读取 VM 对象布局。
- 发布用静态脚本清单和类型工厂替代程序集属性扫描、反射未初始化对象分配。工厂在 GodotObject 基类构造时关联已有原生对象，再执行正常字段初始化和用户构造函数；构造上下文按类型匹配并以 try/finally 恢复，支持嵌套。
- LeanCLR 通过公共 engine_host 启动和停止，通过生成的静态 registry 注册 calli 桥。只有生成代码包含 runtime 的生成器 ABI 头文件，宿主本身只使用公共接口。
- 独立发布目录按实际程序集引用闭包打包：39 个托管文件，约 31.7 MB。CoreLib 验证锁定哈希，开发目录不被发布构建污染。

## 边界

M1 是 Windows 垂直样例，不是完整 Godot C# 兼容性承诺。当前工厂只支持已登记脚本的无参构造；额外脚本、带参构造、完整信号/资源/集合/删除后访问、异步和线程契约按 M2 继续验证。当前模板使用 optimize=none 方便快速迭代，体积和性能不代表 M5 的发布结果。

全量 GodotSharp calli 闭包扫描触发过泛型预算保护，因此使用官方互操作签名目录作为有界输入。运行时程序集属性扫描与 RuntimeHelpers.GetUninitializedObject 路径也遇到兼容性失败；静态注册与生成工厂是发布后端的正式替代路径，未在 LeanCLR 核心留下本地补丁。

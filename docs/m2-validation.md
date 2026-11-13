# M2 对象与脚本语义验收

状态：已完成 Windows x64 阶段验收。

```powershell
python tools/test-m2.py
```

同一个 `samples/semantics` 工程在官方 .NET 和 LeanCLR 发布后端执行。脚本从实际编译程序集的 ScriptPath 元数据生成登记表，覆盖抽象基类、Node2D 子类和 Resource 子类，不再将注册逻辑固定为 Player。

15 项检查：继承、导出 Resource、资源包装身份、泛型 Array、泛型 Dictionary、Variant 转换、同步信号、断开信号、PackedScene 实例化、GC 后对象/资源存活、Free、删除后访问、重复对象与信号生命周期、资源保存、资源回读。

验证运行三次独立的发布进程，每次执行 32 轮节点创建/删除和信号连接/触发/断开，中间主动 GC。全部结果与官方 .NET 基线一致：

```text
M2_SEMANTICS_OK checks=15 observed=31
M2_ALL_OK contracts=15 fresh_process_runs=3 resource_leaks=0
```

退出日志未出现 ObjectDB 泄漏、仍在使用的资源或未回收 StringName。报告：`build/m2/validation.json`。

## 生命周期修复

最初 PackedScene 包装在 GC 后进入待终结队列，其弱跟踪记录已经失效，退出时出现原生资源引用残留。发布 GodotSharp 现在在原生脚本系统关闭前、仍处于 owner 线程且回调有效时，执行一次 GC 并排空待终结队列，再复用官方 DisposablesTracker 顺序释放 Godot 对象和其他封送资源。没有在每帧强制全量 GC，也没有修改 LeanCLR 核心。

全部反向回调增加 owner 线程校验；非法线程进入不能静默破坏单线程 VM，也不通过排队改变同步信号语义。当前阶段不承诺任意后台线程调用 Godot API。

## 工具和边界

- 元数据工具检查脚本路径、类型形态和公开无参构造；不支持的构造方式在发布生成阶段拒绝。
- 抽象脚本仅注册类型/路径，实际实例化由 Godot 的抽象标记阻止。
- 发布 staging 按样例隔离，并清除已删除的源资源，避免不同样例混包。
- 原生渲染、physics 和异步 I/O 的全面兼容性不由这 15 个契约推导；后续平台仍需分别执行。
- M2 测试覆盖当前样例代表的信号、资源和集合契约，不表示所有 Godot API、第三方插件及任意泛型组合都已支持。

# LeanCLR 上游 Android 修复验证

日期：2026-11-14。

LeanCLR submodule 已从 `b19308a21dae8c58d3ec4fb7e850e24a565d47f1` 更新到最新 `coreclr-minimal` 的 `7d98994f7954ed637d7a47e9c851170239643353`（`Merge Android POSIX fixes and enable native x86_64 calli`）。其中 zlib 构建修复来自 `952b625`。

## 上游修复核对

| 项目 | 核对结果 |
| --- | --- |
| `kernel32.cpp` | Android 使用 `futimens`；不再要求 API 24 提供 API 26 才引入的 `futimes`。 |
| `rt_sys.cpp` | Android GNU `strerror_r` 使用 `char*` 返回值，并增加 `__ANDROID_API__ >= 23` 条件，兼顾低 API 的声明。 |
| `calli_native.cpp` | 平台准入已包含 Android x64，GodotSharp 的 native calli 不再被原先的平台检查拒绝。 |
| zlib CMake | 上游检测 `unistd.h`，对 vendored zlib C 源文件定义 `HAVE_UNISTD_H=1`，并在适用编译器上启用 `-Werror=implicit-function-declaration`。 |

本仓库已删除 `runtime_patches/android-posix.patch` 和 `tools/prepare_android_runtime.py`，移除宿主 CMake 中的 Android `HAVE_UNISTD_H` 覆盖。Android 构建直接使用 `extern/leanclr`，不再制作或编译补丁源码副本；`-RuntimeSource` 外部源码目录选项保持可用。

构建确认使用 NDK `29.0.14206865`、目标 `android-24` / `x86_64`。CMakeCache 的 `LEANCLR_SOURCE_DIR` 指向官方 submodule，`LEANCLR_ZLIB_HAVE_UNISTD_H=1`；Ninja 中 zlib 编译命令包含上游的头文件宏和隐式函数声明错误检查。submodule 保持干净。

## 执行验证

| 验证 | 结果 |
| --- | --- |
| Android 解释执行 Node2D | MuMu `localhost:7555`，三个独立进程均得到四帧 `x=8`、`speed=120`。 |
| Android 15 项语义契约 | 三个独立进程均通过，覆盖信号、资源、集合、实例化、GC 与释放。 |
| Android 11 项扩展契约 | 三个独立进程均通过，包含 Unicode、文件、Tween、延迟调用和 160 MiB 根存活。 |
| Android 公共 ABI | 同步嵌套调用、递归、GC 根存活、异常传播与恢复、缓冲区所有权均通过。 |
| 上游 bundled zlib 实际 I/O | 链接新编译的 runtime archive，在 MuMu 写入并读回 65,536 字节，反向 seek 到 17 后读回验证，rewind 后再读，内容一致。 |
| Win64 混合 AOT | 实际运行通过，观察到原生 `Step` 入口，最终状态一致。 |
| HTML5 混合 AOT | 真实 Chrome，首次运行加两次刷新均通过，每次均观察到原生 `Step` 入口。 |
| Android 混合 AOT | 三个独立进程通过，每次均观察到原生 `Step` 入口。 |
| Android 试玩包生命周期 | 可见绘制、同进程后台恢复、冷进程重建均通过。 |

日志与收据位于 `build/validation/upstream-7d98994/`。zlib 成功标记为：

```text
ANDROID_ZLIB_IO_OK write=65536 read=65536 seek=17 rewind=true
```

三个目标的解释 / 混合模板共六组缓存均已按新 runtime 重建，模板清单中的 runtime 版本和依赖锁同步更新；Android 的 `runtime_patches` 为空。两个模板 ZIP 也已重新生成并验证文件哈希。

更新后的 Android 试玩包位于 `build/validation/upstream-7d98994/android-playable/demo.apk`，已安装到 MuMu。此前 `build/export/m5/` 下的包保留为历史验收产物，重新发布会使用当前版本的模板缓存。

本次确认上述 Android 构建与运行问题已由上游解决，不再需要对应的本地修复。验收仍限 Android x64 / MuMu；不据此推导 ARM64 已通过。原 M5 性能数据仍是原始基线的测量，本次功能回归不改写那些历史数字。

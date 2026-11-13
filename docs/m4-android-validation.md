# M4 Android execution record

Validated on MuMu at `localhost:7555`, Android API 32, native `x86_64`. This is emulator acceptance, not ARM64 or physical-device acceptance.

- The same `samples/dotnet` C# Node2D passed three fresh processes: one instance, four frames, `x=8`, exported speed 120.
- All 15 `samples/semantics` contracts passed three fresh processes, including 32 object/signal lifetime cycles per process, GC survival, resource saving and exception behavior after Free.
- The public ABI executable passed scalar/struct arguments, synchronous native/managed nesting, deeper recursion, repeated GC root survival, callback exception propagation and recovery.
- An interactive APK rendered the C# blue circle (1,264 matching pixels), survived background/foreground in the same process, and rendered again after force-stop and cold recreation. Backgrounding never stops the VM.
- APK inspection permits only `lib/x86_64/libgodot_android.so` and `libc++_shared.so`; there is no CoreCLR/hostfxr/Mono runtime library.

Receipts: `build/android/validation-{dotnet,semantics}/report.json`, `build/android/abi-run.log`, `build/android/lifecycle/report.json` and PNGs.

## Reproduce

Prepare the isolated SDK with `python tools/prepare_android.py`. It reuses an existing accepted SDK license; it does not accept agreements. Build `tools/build-android-runtime.ps1`, fetch the verified official APK container with `python tools/fetch_templates.py --android`, then run `python tools/prepare_android_template.py`.

```powershell
python tools/prepare_m1_managed.py --sample samples/dotnet
python tools/publish-m1.py --target android --smoke --output build/export/m4/android
python tools/test-android-runtime.py build/export/m4/android/demo.apk
python tools/prepare_m1_managed.py --sample samples/semantics
python tools/publish-m1.py --target android --sample samples/semantics --output build/export/m4/semantics
python tools/test-android-runtime.py build/export/m4/semantics/demo.apk --sample semantics
```

For lifecycle testing publish the Node2D APK without `--smoke`, then use `tools/test-android-lifecycle.py`.

## Portability changes

The pinned official submodule remains clean. `tools/prepare_android_runtime.py` makes a build-only source copy and emits `runtime_patches/android-posix.patch`:

1. Android API 24 uses `futimens` instead of unavailable `futimes`.
2. Bionic's GNU `strerror_r` returns `char*`.
3. Native calli's platform admission includes Android x64, whose generated C++ bridges use the platform C ABI. Other Android architectures stay rejected. This admission was necessary: the original code explicitly allowed only Win64 and Wasm.

The host's zlib target defines `HAVE_UNISTD_H`. These changes contain no managed object-layout substitutions. They should be proposed upstream independently before broad Android architecture support.

The private exporter bypasses the official Mono `.NET 9` template restriction only for an explicit staged LeanCLR payload. It retains Android SDK, Java, texture-import, package and signature checks. Test APKs use a newly generated local Android debug key; production signing and AAB/store publication are outside this acceptance.

The current engine profile omits Swappy and is built without engine optimization for iteration speed. No Android frame-pacing or production performance claim follows from these tests.

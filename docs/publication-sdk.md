# LeanCLR publication SDK

This repository currently supplies a bounded SDK for the three bundled sample profiles, Godot 4.7.2, LeanCLR `coreclr-minimal`, and Win64 / HTML5 / Android x64. It preserves the official .NET editor and uses a separate private exporter. It is not a claim that every Godot or .NET API is supported.

## Build and publish

The Windows build machine needs the pinned Godot sources and private exporter, the official .NET editor alongside this checkout, .NET SDK 10 plus the verified 10.0.8 BCL, MSVC 2022, CMake, Python, SCons, Emscripten 4.0.20, and the isolated Android SDK/JDK described in the validation records. These dependencies are verified or pinned in `dependencies.json`, preparation tools and generated manifests. Accepted Android SDK licenses must already exist. Build and import each sample with the official .NET editor before first publishing and after C# source changes; the private exporter reuses its development script metadata. The current adapter requires the sample `.godot/mono` outputs and reports a missing prerequisite if they are absent.

```powershell
# First build creates a hashed template in build/sdk/templates/<target>/<mode>.
python tools/publish.py --target win64 --sample samples/dotnet --output build/release/windows --build
python tools/publish.py --target html5 --sample samples/dotnet --output build/release/web --build
python tools/publish.py --target android --sample samples/dotnet --output build/release/android --build

# Subsequent publications reuse the exact template; choose a new output directory.
python tools/publish.py --target win64 --sample samples/semantics --output build/release/semantics

# Regenerate native gameplay AOT and publish with full interpreter fallback elsewhere.
python tools/publish.py --target win64 --sample samples/dotnet --output build/release/windows-aot --aot --build
```

Build scripts and the lower-level publisher retain their `RuntimeSource` / `--runtime-source` overrides. The release SDK requires the validated runtime revision; changing that revision is an explicit dependency update and revalidation, not an automatic substitution. Godot source and toolchain preparation are separate from publishing; this is a repository SDK, not a standalone installer.

`--smoke` embeds four-frame deterministic arguments in Android test APKs. Omit it for the playable demo. Current Android packages use a local debug key and the native x64 MuMu ABI. Store signing, AAB, ARM64 and physical devices remain separate work.

## Gates and reports

Every publication rebuilds isolated managed assemblies, verifies the template hashes and versions, computes the managed reference closure, exports into a unique staging directory, scans its metadata and promotes the directory only on success. Existing outputs are preserved. A process-held lock serializes SDK publications over the shared managed build/import caches and is released automatically even when a process exits unexpectedly. Failure leaves `pipeline.log` and diagnostic reports in the staging directory.

- `publication.json`: exact dependencies, target template contract, source and assembly hashes.
- `compatibility.json`: complete closure member/import census, known unsupported application dependencies and profile status.
- `artifacts.json`: pointer/real widths, interpreter or mixed mode, artifact sizes and SHA-256 hashes.
- `template.json`: template, GodotSharp and calli catalog fingerprints; mixed-mode method/IL retention details; Android source patch hashes.

Only exact, executed fixture source profiles in `sdk/validated-profiles.json` receive `validated-fixture` status. Unknown sources require explicit `--experimental`, remain `experimental-pending`, and still cannot publish known unsupported dependencies. The census does not prove reflection-string targets, indirect delegates, asynchronous behavior or all BCL implementations. The official generated `NativeLibrary.SetDllImportResolver` registration is allowed; actual native loading/export operations and user P/Invokes are blocked. HTML5 `Stopwatch` initialization is blocked; use `Godot.Time.GetTicksUsec`.

Before VM initialization, the native host checks Godot/runtime revision, pointer width, float precision, calli catalog, GodotSharp and CoreLib fingerprints. Every loaded DLL must match the manifest hash. Mixed templates additionally require the exact DemoLogic DLL used by LeanAOT. A rejected contract exits without running gameplay. Manifest size, file count, assembly size and file names are bounded. This is compatibility/integrity validation, not a sandbox for untrusted managed code.

The current source adapter compiles top-level sample scripts with public parameterless constructors and generates explicit script paths/factories. Projects with other dependencies, source layouts, constructors or dynamic registrations need additional adapters and execution profiles. Full metadata and IL are retained; reflection is not made safe by stripping everything that the static scanner fails to see.

## Editor entry and CI

```powershell
python tools/install-editor-addon.py samples/dotnet
```

The optional addon adds three `Project > Tools > LeanCLR: Publish ...` entries to the official editor. They start the same SDK command in a separate process and print the output/staging path. The editor continues to use official .NET for Play, reload and debugging. The menu's registration is checked on an isolated copied project with the official headless editor; this does not claim automated IDE breakpoint validation.

`tools/validate-sdk.ps1` executes all nine combinations of target and fixture; `-Build` also rebuilds templates. `.github/workflows/publication.yml` runs it on a prepared self-hosted Windows runner labelled `leanclr-godot`, with Chrome and MuMu at `localhost:7555`. The workflow preserves ignored SDK caches with `clean: false` and explicitly checks the prepared runner checkout with `tools/ci-preflight.ps1`; prepare that checkout, including the sample development builds, before the first dispatch. The workflow is manual and has not been submitted to a remote runner by this task; local execution validates its command chain.

`python tools/pack-templates.py` creates a ZIP with the three interpreter templates, contracts, hashes and notices; `--mode mixed` does the same for AOT templates. These bundles accompany this repository's tools and managed source adapter, rather than replacing the installed editor. They contain no signing keys or production credentials.

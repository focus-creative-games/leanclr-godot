# LeanCLR publication SDK

The publication SDK builds Godot C# games with LeanCLR `coreclr-minimal` for Windows x64, HTML5 and Android x86_64. Development, Play and C# debugging use the official Godot 4.7.2 .NET editor. Publication uses a separate private exporter and LeanCLR runtime templates.

The SDK currently supports the three bundled sample projects. Other projects may require source-adapter changes and additional runtime testing. See the [Demo guide](demo-guide.zh-CN.md) for development, debugging and running published games.

## Prepare dependencies

Run the commands below in Windows PowerShell from the repository root.

```powershell
git submodule update --init --recursive
```

Use the versions pinned in `dependencies.json` and the preparation scripts:

| Dependency | Requirement |
| --- | --- |
| LeanCLR | The submodule revision pinned by this repository, using the `CORECLR_NET10` profile |
| Godot | Pinned 4.7.2 sources and the official 4.7.2 .NET Windows x64 editor |
| .NET | SDK 10 and the 10.0.8 BCL required by the build scripts |
| Windows build tools | MSVC 2022, CMake, Python and SCons 4.8.1 |
| HTML5 | Emscripten 4.0.20, prepared through the repository script |
| Android | JDK, NDK 29.0.14206865, Android platform 36, build-tools 36.1.0 and Platform-Tools |

The publication scripts expect the official editor directory `Godot_v4.7.2-stable_mono_win64` alongside the repository checkout. Keep the original editor executable name inside that directory. Setting an editor variable for interactive use does not change this publisher default.

Prepare the pinned Godot source and build the private exporter:

```powershell
python tools/prepare_godot.py
./tools/build-m0-exporter.ps1
```

The exporter build installs SCons into the repository's `.tools/scons` directory when needed. Prepare the additional toolchains for the targets you plan to publish:

```powershell
# HTML5
python tools/prepare_emsdk.py

# Android
python tools/prepare_android.py
```

Android preparation requires an existing Android SDK under the user's default Android SDK location, with Platform-Tools and accepted SDK licenses. The script copies those files and prepares isolated packages under `.tools/android-sdk`; it does not accept license agreements. Make the JDK's `java` command available on PATH.

Build and import each project with the official .NET editor before its first publication and after C# changes. The exporter requires the project's `.godot/mono` development metadata. Keep the sample's existing development target framework; the publisher builds separate publication assemblies.

Dependency preparation is separate from publishing. `--build` builds the target template; it does not install every prerequisite. The SDK is intended to run from this repository with its tools and source adapter.

## Publish from the command line

Choose a new output directory for every publication. Outputs must be inside the repository, outside `samples`, and must not already exist. Run publications sequentially because they share build and import caches.

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = "build/release/$stamp"

# Build interpreter templates and publish each target.
python tools/publish.py --target win64 --sample samples/dotnet --output "$out/windows" --build
python tools/publish.py --target html5 --sample samples/dotnet --output "$out/web" --build
python tools/publish.py --target android --sample samples/dotnet --output "$out/android" --build

# Reuse a matching interpreter template for another bundled project.
python tools/publish.py --target win64 --sample samples/semantics --output "$out/semantics"

# Build a mixed AOT template and publish with interpreter fallback.
python tools/publish.py --target win64 --sample samples/dotnet --output "$out/windows-aot" --aot --build
```

| Option | Purpose |
| --- | --- |
| `--target` | Required target: `win64`, `html5` or `android` |
| `--sample` | Project directory; defaults to `samples/dotnet` |
| `--output` | Required new publication directory |
| `--build` | Build or rebuild the selected target and execution-mode template |
| `--aot` | Use mixed AOT; currently compiles two DemoLogic methods and interprets the remaining code |
| `--experimental` | Allow a source configuration awaiting runtime verification; known unsupported dependencies are still rejected |
| `--smoke` | Embed automatic test arguments in an Android APK; omit for normal play |
| `--runtime-source` | Use another LeanCLR source directory at the required pinned revision |

Without `--aot`, the SDK uses interpreter templates. Matching templates are cached in `build/sdk/templates/<target>/<mode>`. Each publication rebuilds the managed assemblies even when it reuses a template.

After changing sample code, scenes or resources, build and import the project again, then add `--experimental` to the publish command. If an AOT-compiled assembly changes, also use `--aot --build` for each affected target. A mixed template must match the exact DemoLogic DLL included in the publication.

The `--runtime-source` option changes the source location, not the required runtime version. Updating that version requires updating the dependency contract and testing the resulting runtime, templates and application together.

Android publications currently use a local debug key and target MuMu x86_64. ARM64, physical devices, AAB and store signing are not yet verified publication targets.

## Publish from the editor

Install the optional addon into a sample project:

```powershell
python tools/install-editor-addon.py samples/dotnet
```

Reopen the project or enable the plugin, then choose one of the three `Project > Tools > LeanCLR: Publish ...` entries. Publication runs in a separate process and prints the output or diagnostic directory to the editor console.

The menu uses interpreter templates without `--build` or `--experimental`. Prepare matching templates first. Use the command line for AOT, template rebuilding or modified source configurations. The editor continues to use official .NET for Play, reload and debugging.

## Compatibility and runtime limits

- Scene-instantiable C# scripts must currently be top-level, non-generic public types with public parameterless constructors. Script inheritance and abstract base classes are supported. Other layouts, dependencies, constructors or dynamic registrations may need adapter changes.
- The publication host is single-threaded, with VM calls on the startup thread. The compatibility checker rejects known dependencies on threads, thread pools, `Task.Run`, dynamic code generation, user P/Invokes and native-library loading/export operations. The official generated `NativeLibrary.SetDllImportResolver` registration is allowed.
- GodotSharp exposes the official API surface, but not every Godot or .NET API is implemented or verified. HTML5 `Stopwatch` initialization is blocked; use `Godot.Time.GetTicksUsec` instead.
- Only exact sample source configurations registered in `sdk/validated-profiles.json` receive `validated-fixture` status. Changed or unknown configurations require `--experimental` and remain `experimental-pending`.
- Static scanning cannot establish compatibility for every reflection-string target, indirect delegate, asynchronous operation or BCL implementation. Test the published application on each target. `--experimental` does not add missing runtime capabilities.
- Mixed AOT retains full IL and metadata and uses interpreter fallback for the remaining code.

Before executing gameplay, the host checks the Godot/runtime versions, pointer width, float precision, calli catalog, GodotSharp and CoreLib fingerprints, and loaded DLL hashes. Mixed templates also check the AOT assembly identity. Contract mismatches stop startup. Manifest size, file count, assembly size and file names are bounded. These checks provide compatibility and integrity validation; they do not sandbox untrusted managed code.

## Publication reports and failures

Publication verifies template versions and hashes, builds the managed dependency closure, exports into a staging directory and checks compatibility before creating the final output directory. Existing output directories are preserved. A process-held lock prevents concurrent SDK publications and is released when the publisher exits.

| File | Contents |
| --- | --- |
| `publication.json` | Dependency versions, source and assembly hashes, and the embedded target template contract |
| `compatibility.json` | Managed dependency member/import inventory, known unsupported dependencies and source-profile status |
| `artifacts.json` | Target, pointer and real widths, interpreter or mixed mode, artifact sizes and SHA-256 hashes |
| `template.json` | Cached template file hashes, GodotSharp and calli fingerprints, and mixed-mode method/IL retention information |
| `pipeline.log` | Build, export and compatibility-check output |

`template.json` is stored with the cached template; its contract is also embedded in `publication.json`. Successful publications contain the publication, compatibility and artifact reports. Failures after staging begins leave diagnostics in a staging directory beside the requested output. Follow the terminal's diagnostic path and inspect `pipeline.log` and any generated reports. Failures before staging, such as missing development metadata or an existing output directory, are reported directly in the terminal.

For missing or mismatched templates, rebuild with `--build`. For an AOT assembly mismatch, use `--aot --build`. For rejected source configurations, inspect `compatibility.json`: changed sources may require `--experimental`, while unsupported dependencies require application changes. More troubleshooting steps are in the [Demo guide](demo-guide.zh-CN.md).

## CI usage

The repository provides a manually triggered GitHub Actions workflow in `.github/workflows/publication.yml`. It requires a prepared self-hosted runner with the labels `self-hosted`, `Windows`, `X64` and `leanclr-godot`.

Prepare the actual checkout used by that runner before dispatching the workflow:

1. Install the pinned editor and build dependencies, prepare the private exporter and all three target toolchains.
2. Build and import `samples/dotnet`, `samples/semantics` and `samples/extended` with the official .NET editor.
3. Install Chrome at the location expected by `tools/test-web-runtime.py` and install its Playwright Python dependency in `.tools/browser`.
4. Start MuMu x64 and ensure ADB can access it at `localhost:7555`. Android checks install and run test APKs on this emulator.
5. Run the preflight check from the runner checkout.

```powershell
python -m pip install --target .tools/browser playwright
./tools/ci-preflight.ps1
```

Preflight checks required checkout files and tool availability; it does not replace browser, emulator or runtime checks. To run the same publication matrix locally:

```powershell
# Build interpreter templates, publish and run all target/sample combinations.
./tools/validate-sdk.ps1 -Build

# Reuse existing matching interpreter templates.
./tools/validate-sdk.ps1
```

The matrix covers all nine combinations of `win64`, `html5`, `android` and the three bundled samples. It checks interpreter publications; mixed AOT requires separate publication and runtime checks. The script prints the report directory on success and writes an aggregate `report.json` under `build/ci`, alongside per-publication reports and runtime logs.

To run on GitHub, open the repository's **Actions** tab, select **LeanCLR publication contracts**, and choose **Run workflow** for the desired branch. The workflow checks out submodules, runs preflight and invokes `tools/validate-sdk.ps1 -Build`. It uses `clean: false` to preserve prepared dependencies and ignored caches in the runner checkout. These dependencies are not supplied by a standard GitHub-hosted runner.

Download the `publication-receipts` artifact from the workflow run for the collected JSON reports and logs. The upload step runs even if an earlier step fails; files available depend on how far the publication progressed. Check the job log for preparation errors or missing artifacts.

## Package templates

After building templates for all three targets in the desired mode, create a bundle:

```powershell
python tools/pack-templates.py
python tools/pack-templates.py --mode mixed
```

The default command packages interpreter templates; `--mode mixed` packages mixed AOT templates. ZIP files are written under `build/sdk/dist` and include template contracts, file hashes and third-party notices. Packaging checks template file hashes before writing the bundle. The packaging script also expects .NET license files at its configured Windows installation location.

Template bundles accompany the repository tools and managed source adapter. They do not replace the official editor or include signing keys. See [third-party notices](../THIRD_PARTY_NOTICES.md) for licensing information.

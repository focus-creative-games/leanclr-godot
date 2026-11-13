"""Build isolated publication assemblies from official GodotSharp and sample sources."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--godot-mono', type=Path, default=ROOT.parent / 'Godot_v4.7.2-stable_mono_win64')
parser.add_argument('--sample', type=Path, default=ROOT / 'samples/dotnet')
args = parser.parse_args()
build = ROOT / 'build/m1'
build.mkdir(parents=True, exist_ok=True)
godot = args.godot_mono / 'Godot_v4.7.2-stable_mono_win64_console.exe'
generated = build / 'glue/GodotSharp/GodotSharp/Generated'
if not generated.exists():
    subprocess.run([str(godot), '--headless', '--editor', '--generate-mono-glue', str(build / 'glue')], check=True)
source = ROOT / 'extern/godot/modules/mono/glue/GodotSharp'
stage = build / 'managed/GodotSharp'
stage.mkdir(parents=True, exist_ok=True)
for name in ['Core', 'Properties']:
    shutil.copytree(source / 'GodotSharp' / name, stage / name, dirs_exist_ok=True)
for name in ['GlobalUsings.cs', 'Compat.cs']:
    shutil.copyfile(source / 'GodotSharp' / name, stage / name)
shutil.copytree(generated, stage / 'Generated', dirs_exist_ok=True)
(stage / 'Core/Bridge/ScriptManagerBridge.publication.cs').write_text('''using System;
using System.Collections.Generic;
namespace Godot.Bridge {
 public static partial class ScriptManagerBridge {
  private static readonly Dictionary<Type, Func<GodotObject>> _publishedFactories = new();
  public static void RegisterPublishedScript(Type type, string path, Func<GodotObject> factory) {
   _pathTypeBiMap.Add(path, type);
   _publishedFactories.Add(type, factory);
  }
 }
 internal static class PublicationConstruction {
  [ThreadStatic] private static Type _expectedType;
  [ThreadStatic] private static IntPtr _native;
  internal static IntPtr Take(Type actual) {
   if (actual != _expectedType) return IntPtr.Zero;
   IntPtr result = _native;
   _expectedType = null;
   _native = IntPtr.Zero;
   return result;
  }
  internal static GodotObject Construct(Type type, IntPtr native, Func<GodotObject> factory) {
   Type previousType = _expectedType;
   IntPtr previousNative = _native;
   _expectedType = type;
   _native = native;
   try {
    GodotObject instance = factory();
    if (instance.NativePtr != native) throw new InvalidOperationException("Native script constructor association failed.");
    return instance;
   } finally { _expectedType = previousType; _native = previousNative; }
  }
 }
}
''', encoding='utf-8')
script_bridge = stage / 'Core/Bridge/ScriptManagerBridge.cs'
bridge_text = script_bridge.read_text()
method_start = bridge_text.index('internal static unsafe godot_bool CreateManagedForGodotObjectScriptInstance')
body_start = bridge_text.index('                // Performance is not critical here', method_start)
body_end = bridge_text.index('                return godot_bool.True;', body_start)
bridge_text = bridge_text[:body_start] + '''                if (argCount != 0)
                    throw new NotSupportedException("M1 publication factories support parameterless script constructors only.");
                Type scriptType = _scriptTypeBiMap.GetScriptType(scriptPtr);
                PublicationConstruction.Construct(scriptType, godotObject, _publishedFactories[scriptType]);
''' + bridge_text[body_end:]
script_bridge.write_text(bridge_text, encoding='utf-8')
disposables = stage / 'Core/DisposablesTracker.cs'
disposables.write_text(disposables.read_text().replace('                OnGodotShuttingDownImpl();',
    '                GC.Collect();\n                GC.WaitForPendingFinalizers();\n                OnGodotShuttingDownImpl();'), encoding='utf-8')
# A returned native function address has pointer ABI; retaining its nested
# function-pointer metadata is outside the current LeanCLR calli contract.
native = stage / 'Core/NativeInterop/NativeFuncs.cs'
native.write_text(native.read_text().replace('partial delegate* unmanaged<godot_bool, IntPtr> godotsharp_get_class_constructor',
                                             'partial IntPtr godotsharp_get_class_constructor'), encoding='utf-8')
obj = stage / 'Core/GodotObject.base.cs'
obj.write_text(obj.read_text().replace('var nativeConstructor = NativeFuncs.godotsharp_get_class_constructor(typeSelf);',
    'var nativeConstructor = (delegate* unmanaged<godot_bool, IntPtr>)(void*)NativeFuncs.godotsharp_get_class_constructor(typeSelf);')
    .replace('_memoryOwn = memoryOwn;', '_memoryOwn = memoryOwn;\n            NativePtr = PublicationConstruction.Take(GetType());'), encoding='utf-8')
internal_analyzer = source / 'Godot.SourceGenerators.Internal/bin/Debug/netstandard2.0/Godot.SourceGenerators.Internal.dll'
project = f'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework><AssemblyName>GodotSharp</AssemblyName>
    <AssemblyVersion>4.7.2.0</AssemblyVersion><AllowUnsafeBlocks>true</AllowUnsafeBlocks>
    <DefineConstants>GODOT</DefineConstants><EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <NoWarn>1591;8632</NoWarn><GenerateDocumentationFile>false</GenerateDocumentationFile>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="Core/**/*.cs" /><Compile Include="Generated/**/*.cs" />
    <Compile Include="Properties/**/*.cs" /><Compile Include="GlobalUsings.cs" /><Compile Include="Compat.cs" />
    <Analyzer Include="{internal_analyzer.as_posix()}" />
  </ItemGroup>
</Project>'''
(stage / 'GodotSharp.csproj').write_text(project, encoding='utf-8')
subprocess.run(['dotnet', 'build', str(stage / 'GodotSharp.csproj'), '-c', 'Release', '--nologo'], check=True)
print('M1 publication GodotSharp built in', stage / 'bin/Release/net10.0')
fixture = build / 'signature-fixture'
fixture.mkdir(parents=True, exist_ok=True)
declarations = native.read_text()
declarations = declarations[declarations.index('        // Custom functions'):]
header = '''using System;
using Godot;
using Godot.NativeInterop;
using Godot.SourceGenerators.Internal;
namespace Godot.NativeInterop {
[GenerateUnmanagedCallbacks(typeof(UnmanagedCallbacks))]
public static unsafe partial class NativeFuncs {
private partial struct UnmanagedCallbacks { }
'''
(fixture / 'NativeSignatures.cs').write_text(header + declarations, encoding='utf-8')
(fixture / 'AdditionalSignatures.cs').write_text('''using System;
using Godot.NativeInterop;
public static unsafe class AdditionalSignatures {
 public static IntPtr Constructor(IntPtr p, godot_bool b) => ((delegate* unmanaged<godot_bool, IntPtr>)(void*)p)(b);
 public static void Properties(IntPtr p, IntPtr script, godot_string* name, void* data, int count) => ((delegate* unmanaged<IntPtr, godot_string*, void*, int, void>)(void*)p)(script, name, data, count);
 public static void Defaults(IntPtr p, IntPtr script, void* data, int count) => ((delegate* unmanaged<IntPtr, void*, int, void>)(void*)p)(script, data, count);
}
''', encoding='utf-8')
(fixture / 'Signatures.csproj').write_text(f'''<Project Sdk="Microsoft.NET.Sdk">
 <PropertyGroup><TargetFramework>net10.0</TargetFramework><AssemblyName>GodotSharpEditor</AssemblyName><AllowUnsafeBlocks>true</AllowUnsafeBlocks><NoWarn>0436;0169</NoWarn></PropertyGroup>
 <ItemGroup><Reference Include="GodotSharp"><HintPath>{stage.as_posix()}/bin/Release/net10.0/GodotSharp.dll</HintPath></Reference>
 <Analyzer Include="{internal_analyzer.as_posix()}" /></ItemGroup>
</Project>''', encoding='utf-8')
subprocess.run(['dotnet', 'build', str(fixture / 'Signatures.csproj'), '-c', 'Release', '--nologo'], check=True)
game = build / 'managed/Gameplay'
game.mkdir(parents=True, exist_ok=True)
source_files = sorted(args.sample.glob('*.cs'))
if not source_files:
    raise RuntimeError('No script source files in sample')
for old in game.glob('*.cs'):
    if old.name not in {path.name for path in source_files}:
        old.unlink()
for source_file in source_files:
    shutil.copyfile(source_file, game / source_file.name)
public_analyzer = ROOT / 'extern/godot/modules/mono/editor/Godot.NET.Sdk/Godot.SourceGenerators/bin/Debug/netstandard2.0/Godot.SourceGenerators.dll'
(game / 'Gameplay.csproj').write_text(f'''<Project Sdk="Microsoft.NET.Sdk">
 <PropertyGroup><TargetFramework>net10.0</TargetFramework><GodotProjectDir>{game.as_posix()}/</GodotProjectDir><AllowUnsafeBlocks>true</AllowUnsafeBlocks></PropertyGroup>
 <ItemGroup><CompilerVisibleProperty Include="GodotProjectDir" />
 <Reference Include="GodotSharp"><HintPath>{stage.as_posix()}/bin/Release/net10.0/GodotSharp.dll</HintPath></Reference>
 <Analyzer Include="{public_analyzer.as_posix()}" /><AssemblyMetadata Include="M0Revision" Value="1" /></ItemGroup>
</Project>''', encoding='utf-8')
subprocess.run(['dotnet', 'build', str(game / 'Gameplay.csproj'), '-c', 'Release', '--nologo'], check=True)
bootstrap = build / 'managed/Bootstrap'
bootstrap.mkdir(parents=True, exist_ok=True)
shutil.copyfile(ROOT / 'managed/m1/Bootstrap.cs', bootstrap / 'Bootstrap.cs')
inspector = ROOT / 'tools/managed-info/bin/Release/net10.0/ManagedInfo.dll'
subprocess.run(['dotnet', 'build', str(ROOT / 'tools/managed-info/ManagedInfo.csproj'), '-c', 'Release', '--nologo'], check=True)
scripts = json.loads(subprocess.check_output(['dotnet', str(inspector), '--scripts', str(game / 'bin/Release/net10.0/Gameplay.dll')], text=True))
registration = ['namespace LeanClr { public static partial class Bootstrap { static partial void RegisterScripts() {']
for script in scripts:
    factory = 'null' if script['abstractType'] else '() => new global::' + script['type'] + '()'
    registration.append(f'Godot.Bridge.ScriptManagerBridge.RegisterPublishedScript(typeof(global::{script["type"]}), {json.dumps(script["path"])}, {factory});')
registration.append('} } }')
(bootstrap / 'Registration.cs').write_text('\n'.join(registration), encoding='utf-8')
(build / 'scripts.json').write_text(json.dumps(scripts, indent=2) + '\n', encoding='utf-8')
(bootstrap / 'Bootstrap.csproj').write_text(f'''<Project Sdk="Microsoft.NET.Sdk">
 <PropertyGroup><TargetFramework>net10.0</TargetFramework><AssemblyName>LeanClr.Bootstrap</AssemblyName></PropertyGroup>
 <ItemGroup><Reference Include="GodotSharp"><HintPath>{stage.as_posix()}/bin/Release/net10.0/GodotSharp.dll</HintPath></Reference>
 <Reference Include="Gameplay"><HintPath>{game.as_posix()}/bin/Release/net10.0/Gameplay.dll</HintPath></Reference></ItemGroup>
</Project>''', encoding='utf-8')
subprocess.run(['dotnet', 'build', str(bootstrap / 'Bootstrap.csproj'), '-c', 'Release', '--nologo'], check=True)

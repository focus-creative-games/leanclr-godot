using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Json;

if (args.Length >= 2 && args[0] == "--scan")
{
    var assemblies = new List<object>();
    foreach (string path in args.Skip(1))
    {
        using var stream = File.OpenRead(path);
        using var pe = new PEReader(stream);
        var reader = pe.GetMetadataReader();
        var members = new SortedSet<string>(StringComparer.Ordinal);
        var imports = new List<string>();
        foreach (var handle in reader.MemberReferences)
        {
            var member = reader.GetMemberReference(handle);
            if (member.Parent.Kind != HandleKind.TypeReference) continue;
            var type = reader.GetTypeReference((TypeReferenceHandle)member.Parent);
            members.Add(reader.GetString(type.Namespace) + "." + reader.GetString(type.Name) + "::" + reader.GetString(member.Name));
        }
        foreach (var handle in reader.MethodDefinitions)
        {
            var method = reader.GetMethodDefinition(handle);
            if ((method.Attributes & System.Reflection.MethodAttributes.PinvokeImpl) == 0) continue;
            var import = method.GetImport();
            imports.Add(reader.GetString(reader.GetModuleReference(import.Module).Name) + "!" + reader.GetString(import.Name));
        }
        assemblies.Add(new { assembly = reader.GetString(reader.GetAssemblyDefinition().Name), members, imports });
    }
    Console.WriteLine(JsonSerializer.Serialize(assemblies));
    return 0;
}

if (args.Length == 2 && args[0] == "--scripts")
{
    using var stream = File.OpenRead(args[1]);
    using var pe = new PEReader(stream);
    var reader = pe.GetMetadataReader();
    var scripts = new List<object>();
    foreach (var handle in reader.TypeDefinitions)
    {
        var type = reader.GetTypeDefinition(handle);
        foreach (var attributeHandle in type.GetCustomAttributes())
        {
            var attribute = reader.GetCustomAttribute(attributeHandle);
            if (attribute.Constructor.Kind != HandleKind.MemberReference) continue;
            var ctor = reader.GetMemberReference((MemberReferenceHandle)attribute.Constructor);
            if (ctor.Parent.Kind != HandleKind.TypeReference) continue;
            var attributeType = reader.GetTypeReference((TypeReferenceHandle)ctor.Parent);
            if (reader.GetString(attributeType.Namespace) != "Godot" || reader.GetString(attributeType.Name) != "ScriptPathAttribute") continue;
            var value = reader.GetBlobReader(attribute.Value);
            if (value.ReadUInt16() != 1) throw new InvalidDataException("Invalid script attribute");
            string path = value.ReadSerializedString();
            string name = reader.GetString(type.Name);
            string ns = reader.GetString(type.Namespace);
            bool abstractType = (type.Attributes & System.Reflection.TypeAttributes.Abstract) != 0;
            bool constructor = type.GetMethods().Any(methodHandle => {
                var method = reader.GetMethodDefinition(methodHandle);
                if (reader.GetString(method.Name) != ".ctor" || (method.Attributes & System.Reflection.MethodAttributes.MemberAccessMask) != System.Reflection.MethodAttributes.Public) return false;
                var signature = reader.GetBlobReader(method.Signature);
                _ = signature.ReadSignatureHeader();
                return signature.ReadCompressedInteger() == 0;
            });
            if (name.Contains('`') || !type.GetDeclaringType().IsNil || (!abstractType && !constructor))
                throw new InvalidDataException("Publication requires a non-generic, top-level script with a public parameterless constructor: " + name);
            scripts.Add(new { type = string.IsNullOrEmpty(ns) ? name : ns + "." + name, path, abstractType });
        }
    }
    Console.WriteLine(JsonSerializer.Serialize(scripts));
    return 0;
}
if (args.Length < 2) return 2;
var bcl = Path.GetFullPath(args[0]);
var roots = args.Skip(1).Select(Path.GetFullPath).ToArray();
var selected = roots.ToDictionary(Path.GetFileNameWithoutExtension, StringComparer.OrdinalIgnoreCase);
var queue = new Queue<string>(roots);
var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
var output = new List<object>();
while (queue.TryDequeue(out var path))
{
    if (!visited.Add(path)) continue;
    using var stream = File.OpenRead(path);
    using var pe = new PEReader(stream);
    if (!pe.HasMetadata) throw new InvalidDataException("Not a managed assembly: " + path);
    var reader = pe.GetMetadataReader();
    string name = reader.GetString(reader.GetAssemblyDefinition().Name);
    if (name != Path.GetFileNameWithoutExtension(path)) throw new InvalidDataException("Assembly/file identity mismatch: " + path);
    var references = new List<string>();
    foreach (var handle in reader.AssemblyReferences)
    {
        string dependency = reader.GetString(reader.GetAssemblyReference(handle).Name);
        references.Add(dependency);
        if (!selected.TryGetValue(dependency, out var dependencyPath))
        {
            dependencyPath = Path.Combine(bcl, dependency + ".dll");
            if (!File.Exists(dependencyPath)) throw new FileNotFoundException("Unresolved dependency: " + dependency, path);
            selected.Add(dependency, dependencyPath);
        }
        queue.Enqueue(dependencyPath);
    }
    stream.Position = 0;
    string sha256 = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    output.Add(new { name, path, sha256, references });
}
Console.WriteLine(JsonSerializer.Serialize(output));
return 0;

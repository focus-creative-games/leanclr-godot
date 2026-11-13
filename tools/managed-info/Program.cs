using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Json;

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

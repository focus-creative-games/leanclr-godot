using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace GodotTools.Export
{
    public partial class ExportPlugin
    {
        private static string? LeanClrM0Stage => Environment.GetEnvironmentVariable("GODOT_LEANCLR_M0_STAGE");

        private bool ExportLeanClrM0()
        {
            if (string.IsNullOrEmpty(LeanClrM0Stage))
                return false;
            string stage = Path.GetFullPath(LeanClrM0Stage);
            string manifestPath = Path.Combine(stage, "manifest.json");
            byte[] manifestBytes = File.ReadAllBytes(manifestPath);
            using JsonDocument document = JsonDocument.Parse(manifestBytes);
            JsonElement manifest = document.RootElement;
            if (manifest.GetProperty("phase").GetString() != "M0-export-prototype" ||
                manifest.GetProperty("runtime_ready").GetBoolean() ||
                manifest.GetProperty("godot_commit").GetString() != "ed1daf0bf001b61586d9930840f2f1394092c079")
                throw new InvalidDataException("Invalid M0 export manifest. This helper does not publish runnable C# games.");
            string target = manifest.GetProperty("target").GetString()!;
            string expectedOs = target == "native" ? "Windows" : target == "wasm" ? "Web" : "invalid";
            if (!string.Equals(GetExportPlatform().GetOsName(), expectedOs, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("M0 payload does not match the export platform.");

            // Validate the entire payload before adding any export files.
            foreach (JsonElement entry in manifest.GetProperty("files").EnumerateArray())
            {
                string relative = entry.GetProperty("source").GetString()!;
                string path = entry.GetProperty("path").GetString()!;
                if (Path.GetFileName(relative) != relative || !path.StartsWith("res://.leanclr/", StringComparison.Ordinal) || path.Contains(".."))
                    throw new InvalidDataException("M0 payload path escapes its staging namespace.");
                byte[] data = File.ReadAllBytes(Path.Combine(stage, relative));
                string actual = Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
                if (actual != entry.GetProperty("sha256").GetString())
                    throw new InvalidDataException("M0 payload hash mismatch: " + path);
            }
            foreach (JsonElement entry in manifest.GetProperty("files").EnumerateArray())
                AddFile(entry.GetProperty("path").GetString()!,
                    File.ReadAllBytes(Path.Combine(stage, entry.GetProperty("source").GetString()!)), remap: false);
            AddFile("res://.leanclr/manifest.json", manifestBytes, remap: false);
            Console.WriteLine("M0_EXPORT_PAYLOAD_OK target=" + target);
            return true;
        }
    }
}

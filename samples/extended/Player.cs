using Godot;
using System;

public partial class Player : Node2D
{
    private int checks;
    private bool deferred;
    private Node2D doomed;
    private int frames;

    private void Check(bool condition, string name)
    {
        if (!condition) throw new InvalidOperationException(name);
        checks++;
        GD.Print("M5_PASS " + name);
    }

    public override void _Ready()
    {
        try
        {
            const string unicode = "LeanCLR 中文 😀";
            using var name = new StringName(unicode);
            Check(name.ToString() == unicode, "unicode-stringname-roundtrip");
            var child = new Node2D { Name = "Child" };
            AddChild(child);
            using var path = new NodePath("Child");
            Check(ReferenceEquals(GetNode<Node2D>(path), child), "nodepath-wrapper-identity");
            child.AddToGroup("m5");
            var grouped = GetTree().GetNodesInGroup("m5");
            using var ownedGrouped = (Godot.Collections.Array)grouped;
            Check(grouped.Count == 1 && grouped[0] == child, "scene-groups");
            Position = new Vector2(5, 7);
            Rotation = .3f;
            var point = new Vector2(2, 4);
            Check(ToLocal(ToGlobal(point)).IsEqualApprox(point), "native-transform-roundtrip");
            using var dictionary = new Godot.Collections.Dictionary { ["value"] = 42, ["text"] = unicode };
            string json = Json.Stringify(dictionary);
            using var parsed = Json.ParseString(json).AsGodotDictionary();
            Check(parsed["value"].AsInt32() == 42 && parsed["text"].AsString() == unicode, "json-variant-roundtrip");
            const string filePath = "user://m5-unicode.txt";
            using (var file = Godot.FileAccess.Open(filePath, Godot.FileAccess.ModeFlags.Write)) file.StoreString(unicode);
            using (var file = Godot.FileAccess.Open(filePath, Godot.FileAccess.ModeFlags.Read))
                Check(file.GetAsText() == unicode, "fileaccess-unicode");
            DirAccess.RemoveAbsolute(ProjectSettings.GlobalizePath(filePath));
            const string bytesPath = "user://m5-bytes.bin";
            using (var file = Godot.FileAccess.Open(bytesPath, Godot.FileAccess.ModeFlags.Write)) file.StoreBuffer(new byte[] { 0, 1, 127, 255 });
            using (var file = Godot.FileAccess.Open(bytesPath, Godot.FileAccess.ModeFlags.Read))
            {
                byte[] bytes = file.GetBuffer(4);
                Check(bytes.Length == 4 && bytes[2] == 127 && bytes[3] == 255, "packed-byte-array");
            }
            DirAccess.RemoveAbsolute(ProjectSettings.GlobalizePath(bytesPath));
            using var tween = CreateTween();
            using var property = new NodePath("position");
            tween.TweenProperty(child, property, new Vector2(15, 20), .25);
            tween.CustomStep(1);
            Check(child.Position.IsEqualApprox(new Vector2(15, 20)), "tween-property");
            Callable.From(() => deferred = true).CallDeferred();
            doomed = child;
            child.QueueFree();

            // Retained data exceeds the Web template's initial 128 MiB memory.
            // Touch both ends of every array and verify roots after collection.
            var roots = new byte[5][];
            for (int i = 0; i < roots.Length; ++i)
            {
                roots[i] = new byte[32 * 1024 * 1024];
                roots[i][0] = (byte)(i + 1);
                roots[i][roots[i].Length - 1] = (byte)(i + 2);
            }
            ulong start = Time.GetTicksUsec();
            GC.Collect();
            ulong elapsed = Time.GetTicksUsec() - start;
            for (int i = 0; i < roots.Length; ++i)
                if (roots[i][0] != i + 1 || roots[i][roots[i].Length - 1] != i + 2) throw new InvalidOperationException("memory roots");
            Check(true, "large-heap-GC-root-survival");
            GD.Print($"M5_MEMORY retained_bytes={5 * 32 * 1024 * 1024} gc_ticks={elapsed} frequency=1000000");
            GC.KeepAlive(roots);
        }
        catch (Exception exception) { Fail(exception); }
    }

    public override void _Process(double delta)
    {
        if (++frames < 3) return;
        try
        {
            Check(deferred, "main-thread-deferred-call");
            Check(!IsInstanceValid(doomed), "queued-native-object-free");
            GD.Print($"M5_EXTENDED_OK checks={checks}");
            GetTree().Quit();
        }
        catch (Exception exception) { Fail(exception); }
    }

    private void Fail(Exception exception)
    {
        GD.Print("M5_FAIL " + exception);
        GetTree().Quit(1);
    }
}

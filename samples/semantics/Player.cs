using Godot;
using System;

public partial class Player : BasePlayer
{
    [Signal] public delegate void ScoreChangedEventHandler(int value);
    [Export] public StatsResource Config { get; set; }
    private int observed;
    private int checks;

    private void Check(bool condition, string name)
    {
        if (!condition) throw new InvalidOperationException(name);
        checks++;
        GD.Print("M2_PASS " + name);
    }

    private void OnScore(int value) => observed = value;

    public override void _Ready()
    {
        try
        {
            Check(InheritedValue == 7, "script-inheritance");
            Check(Config != null && Config.Bonus == 11, "exported-resource");
            var cached = ResourceLoader.Load<StatsResource>("res://Config.tres");
            Check(ReferenceEquals(cached, Config), "resource-wrapper-identity");

            var array = new Godot.Collections.Array<int> { 1, 2 };
            using var ownedArray = (Godot.Collections.Array)array;
            array.Add(3);
            Check(array.Count == 3 && array[2] == 3, "typed-array");
            var dictionary = new Godot.Collections.Dictionary<string, int> { ["score"] = 17 };
            using var ownedDictionary = (Godot.Collections.Dictionary)dictionary;
            Check(dictionary["score"] == 17, "typed-dictionary");
            Variant integer = 42;
            Variant vector = new Vector2(2, 4);
            Check(integer.AsInt32() == 42 && vector.AsVector2() == new Vector2(2, 4), "variant-conversion");

            ScoreChanged += OnScore;
            EmitSignal(SignalName.ScoreChanged, 23);
            Check(observed == 23, "signal-synchronous-callback");
            ScoreChanged -= OnScore;
            EmitSignal(SignalName.ScoreChanged, 24);
            Check(observed == 23, "signal-disconnect");

            var scene = ResourceLoader.Load<PackedScene>("res://Child.tscn");
            var child = scene.Instantiate<ChildNode>();
            AddChild(child);
            Check(child.Value == 19 && child.GetParent() == this, "packed-scene-instantiation");
            child.Position = new Vector2(3, 5);
            GC.Collect();
            Check(child.Position == new Vector2(3, 5) && Config.Bonus == 11, "object-and-resource-GC-survival");
            RemoveChild(child);
            child.Free();
            Check(!IsInstanceValid(child), "native-object-free");
            bool disposed = false;
            try { _ = child.Position; } catch (ObjectDisposedException) { disposed = true; }
            Check(disposed, "access-after-free");
            for (int index = 0; index < 32; index++)
            {
                var transient = scene.Instantiate<ChildNode>();
                AddChild(transient);
                RemoveChild(transient);
                transient.Free();
                if (IsInstanceValid(transient)) throw new InvalidOperationException("transient native object survived Free");
                ScoreChanged += OnScore;
                EmitSignal(SignalName.ScoreChanged, index);
                ScoreChanged -= OnScore;
                if (observed != index) throw new InvalidOperationException("signal failed during repeated lifetime changes");
                if (index % 8 == 0) GC.Collect();
            }
            Check(true, "repeated-object-and-signal-lifecycle");

            string path = "user://m2-roundtrip.tres";
            Check(ResourceSaver.Save(Config, path) == Error.Ok, "resource-save");
            var restored = ResourceLoader.Load<StatsResource>(path, "", ResourceLoader.CacheMode.Ignore);
            Check(restored != null && restored.Bonus == 11, "resource-roundtrip");
            DirAccess.RemoveAbsolute(ProjectSettings.GlobalizePath(path));
            GD.Print($"M2_SEMANTICS_OK checks={checks} observed={observed}");
            GetTree().Quit();
        }
        catch (Exception exception)
        {
            GD.PushError("M2_FAIL " + exception);
            GetTree().Quit(1);
        }
    }
}

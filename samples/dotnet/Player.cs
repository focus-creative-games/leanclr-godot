using Godot;
using System;
using System.Reflection;

public partial class Player : Node2D
{
    [Export] public float Speed { get; set; } = 60;
    private static int instances;
    private bool smoke;
    private int frames;
    private int drawCalls;

    public override void _Ready()
    {
        smoke = Array.IndexOf(OS.GetCmdlineUserArgs(), "--m0-smoke") >= 0;
        instances++;
        if (smoke) Input.ActionPress("ui_right");
        if (smoke && (instances != 1 || Speed != 120))
        {
            GD.PrintErr("M0_DOTNET_FAIL initial state or exported property");
            GetTree().Quit(1);
        }
    }

    public override void _Process(double delta)
    {
        float direction = Input.GetAxis("ui_left", "ui_right");
        if (smoke && frames == 2) GC.Collect();
        Position += new Vector2(direction * Speed * (float)(smoke ? 1.0 / 60 : delta), 0);
        QueueRedraw();
        if (smoke && ++frames == 4)
        {
            if (Position.X != 8)
            {
                GD.PrintErr("M0_DOTNET_FAIL frame state");
                GetTree().Quit(1);
                return;
            }
            string revision = "missing";
            foreach (var metadata in typeof(Player).Assembly.GetCustomAttributes<AssemblyMetadataAttribute>())
                if (metadata.Key == "M0Revision") revision = metadata.Value;
            GD.Print($"M0_DOTNET_OK revision={revision} instances={instances} x={Position.X}");
            GD.Print($"NODE2D_SMOKE_OK instances={instances} frames={frames} x={Position.X} speed={Speed} draws={drawCalls}");
            Input.ActionRelease("ui_right");
            GetTree().Quit();
        }
    }

    public override void _Draw()
    {
        drawCalls++;
        DrawCircle(new Vector2(100, 100), 20, Colors.CornflowerBlue);
    }
}

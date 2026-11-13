using Godot;
using System;
using System.Reflection;

public partial class Player : Node2D
{
    [Export] public float Speed { get; set; } = 60;
    private static int instances;
    private bool smoke;
    private int frames;

    public override void _Ready()
    {
        smoke = Array.IndexOf(OS.GetCmdlineUserArgs(), "--m0-smoke") >= 0;
        instances++;
        if (smoke && (instances != 1 || Speed != 120))
        {
            GD.PrintErr("M0_DOTNET_FAIL initial state or exported property");
            GetTree().Quit(1);
        }
    }

    public override void _Process(double delta)
    {
        float direction = smoke ? 1 : Input.GetAxis("ui_left", "ui_right");
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
            GetTree().Quit();
        }
    }

    public override void _Draw()
    {
        DrawCircle(new Vector2(100, 100), 20, Colors.CornflowerBlue);
    }
}

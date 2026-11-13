using Godot;
using System;
using System.Reflection;

public partial class Player : Node2D
{
    [Export] public float Speed { get; set; } = 60;
    private static int instances;
    private static readonly StringName LeftAction = new("ui_left");
    private static readonly StringName RightAction = new("ui_right");
    private bool smoke;
    private int frames;
    private int drawCalls;
    private bool profile;
    private long[] frameTicks;
    private long frameAllocations;
    private long gcTicks;

    public override void _Ready()
    {
        profile = Array.IndexOf(OS.GetCmdlineUserArgs(), "--profile") >= 0;
        smoke = profile || Array.IndexOf(OS.GetCmdlineUserArgs(), "--m0-smoke") >= 0;
        if (profile) frameTicks = new long[240];
        instances++;
        if (smoke) Input.ActionPress(RightAction);
        if (Array.IndexOf(OS.GetCmdlineUserArgs(), "--benchmark") >= 0)
        {
            _ = DemoLogic.Motion.Benchmark(10000);
            long start = (long)Time.GetTicksUsec();
            int checksum = DemoLogic.Motion.Benchmark(200000);
            long elapsed = (long)Time.GetTicksUsec() - start;
            GD.Print($"M5_BENCH ticks={elapsed} frequency=1000000 checksum={checksum} managed_bytes={GC.GetTotalMemory(false)}");
            float accumulated = .1f;
            for (int i = 0; i < 100; ++i) accumulated = DemoLogic.Motion.Step(accumulated, -.7f, 1.2345f, .016f);
            GD.Print($"M5_FLOAT bits={BitConverter.SingleToInt32Bits(accumulated)}");
        }
        if (smoke && (instances != 1 || Speed != 120))
        {
            GD.PrintErr("M0_DOTNET_FAIL initial state or exported property");
            GetTree().Quit(1);
        }
    }

    public override void _Process(double delta)
    {
        long allocated = profile ? GC.GetAllocatedBytesForCurrentThread() : 0;
        long start = profile ? (long)Time.GetTicksUsec() : 0;
        float direction = Input.GetAxis(LeftAction, RightAction);
        if (smoke && frames == 2)
        {
            long gcStart = profile ? (long)Time.GetTicksUsec() : 0;
            GC.Collect();
            if (profile) gcTicks = (long)Time.GetTicksUsec() - gcStart;
        }
        Vector2 position = Position;
        position.X = DemoLogic.Motion.Step(position.X, direction, Speed, (float)(smoke ? 1.0 / 60 : delta));
        Position = position;
        QueueRedraw();
        if (profile)
        {
            frameTicks[frames] = (long)Time.GetTicksUsec() - start;
            if (frames >= 8) frameAllocations += GC.GetAllocatedBytesForCurrentThread() - allocated;
        }
        if (smoke && ++frames == (profile ? 240 : 4))
        {
            if (Position.X != (profile ? 480 : 8))
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
            if (profile)
            {
                // Fixed 232-sample diagnostic sort, outside the measured path.
                for (int i = 9; i < 240; ++i)
                {
                    long value = frameTicks[i];
                    int j = i - 1;
                    while (j >= 8 && frameTicks[j] > value) { frameTicks[j + 1] = frameTicks[j]; --j; }
                    frameTicks[j + 1] = value;
                }
                GD.Print($"M5_PROFILE samples=232 p50_ticks={frameTicks[124]} p95_ticks={frameTicks[228]} max_ticks={frameTicks[239]} gc_ticks={gcTicks} allocated_bytes={frameAllocations} frequency=1000000");
            }
            Input.ActionRelease(RightAction);
            GetTree().Quit();
        }
    }

    public override void _Draw()
    {
        drawCalls++;
        DrawCircle(new Vector2(100, 100), 20, Colors.CornflowerBlue);
    }
}

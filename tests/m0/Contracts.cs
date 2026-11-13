using System;
using System.Runtime.InteropServices;

namespace M0
{
    [StructLayout(LayoutKind.Sequential)]
    public struct Pair { public int X; public float Y; }
    public struct References { public int[] First; public int[] Second; }

    public static class Contracts
    {
        public static void Initialize() { }
        public static void Tick(float delta) { }
        public static void Shutdown() { }
        public static int Scalar(int a, int b) => a + b;
        public static Pair Structure(Pair value) => new Pair { X = value.X + 3, Y = value.Y * 2 };
        public static int Throw(int zero) => 10 / zero;
        public static int Leaf(int value)
        {
            GC.Collect();
            var pressure = new int[] { 999, 998 };
            int result = value >= 100 && value < 104 ? NativeStep(value + 1) + 1 : value * 2;
            GC.KeepAlive(pressure);
            return result;
        }

        [DllImport("m0", CallingConvention = CallingConvention.Cdecl)]
        private static extern int NativeStep(int value);

        public static int Nested()
        {
            var root = new References { First = new int[] { 41 }, Second = new int[] { 42 } };
            int result = NativeStep(5);
            return root.First[0] == 41 && root.Second[0] == 42 ? result + root.First[0] : -999;
        }

        public static int NestedDeep() => NativeStep(100);
        public static int NestedRecovery() => NativeStep(6);

        public static int CatchNative()
        {
            try { return NativeStep(-1); }
            catch (DivideByZeroException) { return 19; }
        }
    }
}

using System;
using Godot.Bridge;
using Godot.NativeInterop;

namespace LeanClr
{
    public static partial class Bootstrap
    {
        public static void Initialize() { }
        public static void Tick(float delta) { }
        public static void Shutdown() { }

        public static void Attach(IntPtr functions, int size)
        {
            try
            {
                Console.WriteLine("LEANCLR_ATTACH native-functions");
                NativeFuncs.Initialize(functions, size);
                AlcReloadCfg.Configure(false);
                Console.WriteLine("LEANCLR_ATTACH script-registration");
                RegisterScripts();
                Console.WriteLine("LEANCLR_ATTACH ready");
            }
            catch (Exception exception)
            {
                Console.WriteLine("LEANCLR_ATTACH_ERROR " + exception.GetType().FullName + ": " + exception.Message);
                Console.WriteLine(exception.StackTrace);
                throw;
            }
        }
        static partial void RegisterScripts();
    }
}

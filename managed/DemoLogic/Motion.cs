namespace DemoLogic
{
    public static class Motion
    {
        public static float Step(float position, float axis, float speed, float delta)
        {
            return position + axis * speed * delta;
        }

        public static int Benchmark(int iterations)
        {
            uint hash = 2166136261;
            for (int index = 0; index < iterations; index++)
            {
                hash ^= (uint)index;
                hash *= 16777619;
                hash ^= hash >> 13;
            }
            return unchecked((int)hash);
        }
    }
}

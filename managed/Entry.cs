// Gameplay adapted from leanclr-godot-shimaoye; MIT, Code Philosophy and contributors.
using System;

namespace Demo;

public static unsafe class Entry
{
    private const int MaximumEntities = 64;
    private static readonly int[] entityKinds = new int[MaximumEntities];
    private static readonly int[] entityX = new int[MaximumEntities];
    private static readonly int[] entityY = new int[MaximumEntities];
    private static readonly int[] entitySpeeds = new int[MaximumEntities];
    private static int* input;
    private static int* output;
    private static int ticks;
    private static float millisecondsRemainder;

    public static void AttachBuffersV1(nint inputAddress, nint outputAddress, int capacity, int version)
    {
        if (inputAddress == 0 || outputAddress == 0 || capacity < 208 || version != 1)
            throw new ArgumentException("Invalid host buffers");
        input = (int*)inputAddress;
        output = (int*)outputAddress;
        if (input[0] != 0x4c434752)
            throw new ArgumentException("Invalid input header");
    }

    public static void Initialize()
    {
        Reset();
        ticks = 0;
        millisecondsRemainder = 0;
    }

    public static void Tick(float deltaSeconds)
    {
        if (input == null || output == null)
            throw new InvalidOperationException("Buffers not attached");
        if (input[1] == 1)
            StartGame();
        millisecondsRemainder += deltaSeconds * 1000;
        int elapsed = (int)millisecondsRemainder;
        millisecondsRemainder -= elapsed;
        StepGame(elapsed, input[2], input[3]);
        ticks++;
        Snapshot();
    }

    public static void Shutdown()
    {
        running = false;
        input = null;
        output = null;
    }

    private static int score;
    private static int lives;
    private static int combo;
    private static int remainingMilliseconds;
    private static int playerX;
    private static int invulnerableMilliseconds;
    private static int spawnCountdownMilliseconds;
    private static int entityCount;
    private static uint randomState;
    private static bool running;

    private static void StartGame()
    {
        Reset();
        running = true;
    }

    private static void StepGame(int elapsedMilliseconds, int direction, int pointerX)
    {
        while (running && elapsedMilliseconds > 0)
        {
            int step = elapsedMilliseconds > 16 ? 16 : elapsedMilliseconds;
            Advance(step, direction, pointerX);
            elapsedMilliseconds -= step;
        }
    }

    private static void Snapshot()
    {
        output[0] = 0x4c434752;
        output[1] = 1;
        output[2] = entityCount;
        output[3] = score;
        output[4] = lives;
        output[5] = combo;
        output[6] = remainingMilliseconds;
        output[7] = GetLevel();
        output[8] = playerX / 1000;
        output[9] = invulnerableMilliseconds;
        output[10] = running ? 1 : 0;
        output[11] = ticks;
        for (int i = 0; i < entityCount; i++)
        {
            int offset = 16 + i * 3;
            output[offset] = entityKinds[i];
            output[offset + 1] = entityX[i] / 1000;
            output[offset + 2] = entityY[i] / 1000;
        }
    }

    private static void Reset()
    {
        score = 0;
        lives = 3;
        combo = 1;
        remainingMilliseconds = 60000;
        playerX = 480000;
        invulnerableMilliseconds = 0;
        spawnCountdownMilliseconds = 350;
        entityCount = 0;
        randomState = 0xA341316Cu;
        running = false;
    }

    private static int GetLevel() => 1 + score / 100;

    private static void Advance(int elapsedMilliseconds, int direction, int pointerX)
    {
        remainingMilliseconds -= elapsedMilliseconds;
        if (remainingMilliseconds <= 0)
        {
            remainingMilliseconds = 0;
            running = false;
            return;
        }

        if (pointerX >= 0)
        {
            playerX = pointerX > 942 ? 942000 : pointerX * 1000;
        }
        else
        {
            int movement = direction < 0 ? -1 : direction > 0 ? 1 : 0;
            playerX += movement * 520 * elapsedMilliseconds;
        }
        if (playerX < 18000)
        {
            playerX = 18000;
        }
        else if (playerX > 942000)
        {
            playerX = 942000;
        }

        invulnerableMilliseconds -= elapsedMilliseconds;
        if (invulnerableMilliseconds < 0)
        {
            invulnerableMilliseconds = 0;
        }

        spawnCountdownMilliseconds -= elapsedMilliseconds;
        if (spawnCountdownMilliseconds <= 0)
        {
            SpawnEntity();
        }

        int index = 0;
        while (index < entityCount)
        {
            entityY[index] += entitySpeeds[index] * elapsedMilliseconds;
            int dx = entityX[index] / 1000 - playerX / 1000;
            int dy = entityY[index] / 1000 - 550;
            int radius = entityKinds[index] == 0 ? 32 : 36;
            if (dx * dx + dy * dy <= radius * radius)
            {
                if (entityKinds[index] == 0)
                {
                    score += 10 * combo;
                    if (combo < 5)
                    {
                        combo++;
                    }
                }
                else if (invulnerableMilliseconds == 0)
                {
                    lives--;
                    combo = 1;
                    invulnerableMilliseconds = 1000;
                    if (lives == 0)
                    {
                        running = false;
                    }
                }

                RemoveEntity(index);
                if (!running)
                {
                    return;
                }
            }
            else if (entityY[index] > 680000)
            {
                RemoveEntity(index);
            }
            else
            {
                index++;
            }
        }
    }

    private static void SpawnEntity()
    {
        int pace = GetLevel();
        if (pace > 12)
        {
            pace = 12;
        }
        spawnCountdownMilliseconds += 620 - pace * 25;
        if (entityCount == MaximumEntities)
        {
            return;
        }

        int index = entityCount++;
        int kind = NextRandom() % 4u == 0 ? 1 : 0;
        entityKinds[index] = kind;
        entityX[index] = (30 + (int)(NextRandom() % 900u)) * 1000;
        entityY[index] = 120000;
        entitySpeeds[index] = 180 + pace * 24 + (kind == 1 ? 45 : 0);
    }

    private static void RemoveEntity(int index)
    {
        int last = --entityCount;
        entityKinds[index] = entityKinds[last];
        entityX[index] = entityX[last];
        entityY[index] = entityY[last];
        entitySpeeds[index] = entitySpeeds[last];
    }

    private static uint NextRandom()
    {
        uint value = randomState;
        value ^= value << 13;
        value ^= value >> 17;
        value ^= value << 5;
        randomState = value;
        return value;
    }
}

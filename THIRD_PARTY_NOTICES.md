# Third party notices

This project uses the upstream LeanCLR `coreclr-minimal` runtime and godot-cpp under their MIT licenses. Source revisions and archive hashes are recorded in `dependencies.json`. Dependency sources retain their original LICENSE files. The LeanCLR runtime is linked without the old fork's CoreLib layout patches.

The sample gameplay in `managed/Entry.cs` is adapted from [shimaoye/leanclr-godot](https://github.com/shimaoye/leanclr-godot), under its MIT license:

Copyright (c) 2026 Code Philosophy(代码哲学)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The Emscripten preparation script is adapted from that project's pinned toolchain preparation script. Emscripten and LLVM retain their own license files in the downloaded SDK.

.NET 10.0.8 managed libraries are distributed with the original `LICENSE.txt` and `ThirdPartyNotices.txt`, staged under `demo/managed/notices` and copied into exported packages. Godot Engine's license and third-party notices are available from its distribution and [official license page](https://godotengine.org/license/).

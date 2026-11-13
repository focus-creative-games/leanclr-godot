#pragma once
#include <godot_cpp/classes/node.hpp>
#include <godot_cpp/variant/packed_int32_array.hpp>
#include <array>
#include "engine_host.h"

namespace godot
{
class LeanCLRHost : public Node
{
    GDCLASS(LeanCLRHost, Node)
    static constexpr int32_t magic = 0x4c434752;
    std::array<int32_t, 4> input_{{magic, 0, 0, -1}};
    std::array<int32_t, 208> output_{};
    LeanclrEngineSession* session_ = nullptr;
    bool ready_ = false;
    String error_;
    uint32_t acquired_ = 0;
    uint32_t released_ = 0;
    static int32_t load_file(void*, const char*, const char*, LeanclrEngineFile*);
    static void release_file(void*, LeanclrEngineFile*);
    static uint64_t thread_id(void*);
    bool attach_buffers();
    bool check(LeanclrEngineStatus, const LeanclrEngineError&);

  protected:
    static void _bind_methods();

  public:
    void _ready() override;
    void _exit_tree() override;
    bool is_runtime_ready() const;
    String get_last_error() const;
    void step_game(double delta, int64_t direction, int64_t pointer_x, bool restart);
    PackedInt32Array get_snapshot() const;
};
} // namespace godot

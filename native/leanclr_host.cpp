#include "leanclr_host.h"
#include "leanclr.h"
#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/classes/file_access.hpp>
#include <godot_cpp/classes/os.hpp>
#include <godot_cpp/variant/utility_functions.hpp>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <new>

namespace godot
{
namespace
{
LeanCLRHost* owner = nullptr;
}

int32_t LeanCLRHost::load_file(void* context, const char* name, const char* extension, LeanclrEngineFile* file)
{
    auto* host = static_cast<LeanCLRHost*>(context);
    if (std::strcmp(extension, "dll") != 0)
        return 0;
    if (std::strcmp(name, "Demo.Managed") != 0 && std::strcmp(name, "System.Private.CoreLib") != 0 && std::strcmp(name, "System.Runtime") != 0)
        return 0;
#ifdef __EMSCRIPTEN__
    const String directory = "res://managed/wasm/";
#else
    const String directory = "res://managed/native/";
#endif
    const String path = directory + String(name) + ".dll.bytes";
    if (!FileAccess::file_exists(path))
        return 0;
    auto source = FileAccess::open(path, FileAccess::READ);
    if (source.is_null() || source->get_length() == 0 || source->get_length() > 64 * 1024 * 1024)
        return -1;
    auto* bytes = new (std::nothrow) PackedByteArray(source->get_buffer(source->get_length()));
    if (!bytes || bytes->is_empty())
    {
        delete bytes;
        return -1;
    }
    file->data = bytes->ptr();
    file->length = static_cast<size_t>(bytes->size());
    file->token = bytes;
    ++host->acquired_;
    return 1;
}

void LeanCLRHost::release_file(void* context, LeanclrEngineFile* file)
{
    delete static_cast<PackedByteArray*>(file->token);
    ++static_cast<LeanCLRHost*>(context)->released_;
}

uint64_t LeanCLRHost::thread_id(void*)
{
    return OS::get_singleton()->get_thread_caller_id();
}

bool LeanCLRHost::check(LeanclrEngineStatus status, const LeanclrEngineError& error)
{
    if (status == LEANCLR_ENGINE_OK)
        return true;
    error_ = String(error.message) + " (status=" + String::num_int64(status) + ", runtime=" + String::num_int64(error.runtime_error) + ")";
    UtilityFunctions::push_error(error_);
    ready_ = false;
    return false;
}

bool LeanCLRHost::attach_buffers()
{
    LeanclrException* exception = nullptr;
    auto* assembly = leanclr_get_assembly("Demo.Managed");
    auto* module = assembly ? leanclr_get_module_by_assembly(assembly) : nullptr;
    auto* klass = module ? leanclr_get_class_by_name(module, "Demo.Entry", false, &exception) : nullptr;
    const auto* method = klass && !exception ? leanclr_get_class_method_by_name(klass, "AttachBuffersV1", &exception) : nullptr;
    if (!method || exception || leanclr_get_total_arg_stack_object_size(method) != 4 || leanclr_get_return_value_stack_object_size(method) != 0)
    {
        error_ = "Demo.Managed buffer contract missing or incompatible";
        return false;
    }
    alignas(8) uint64_t storage[4]{};
    auto* arguments = reinterpret_cast<LeanclrStackObject*>(storage);
    size_t offset = 0;
    const auto input = reinterpret_cast<intptr_t>(input_.data());
    const auto output = reinterpret_cast<intptr_t>(output_.data());
    const int32_t capacity = static_cast<int32_t>(output_.size());
    const int32_t version = 1;
    leanclr_push_argument(arguments, &offset, &input, sizeof(input));
    leanclr_push_argument(arguments, &offset, &output, sizeof(output));
    leanclr_push_argument(arguments, &offset, &capacity, sizeof(capacity));
    leanclr_push_argument(arguments, &offset, &version, sizeof(version));
    leanclr_invoke_with_buffer(method, arguments, nullptr, &exception);
    if (exception)
    {
        error_ = "Demo.Managed rejected buffer contract";
        return false;
    }
    return true;
}

void LeanCLRHost::_ready()
{
    if (Engine::get_singleton()->is_editor_hint())
        return;
    if (owner)
    {
        error_ = "One process-scoped LeanCLRHost is allowed";
        return;
    }
    owner = this;
    LeanclrEngineConfig config{};
    config.size = sizeof(config);
    config.abi_version = LEANCLR_ENGINE_ABI_VERSION;
    config.context = this;
    config.load_file = load_file;
    config.release_file = release_file;
    config.current_thread_id = thread_id;
    config.assembly_name = "Demo.Managed";
    config.entry_type = "Demo.Entry";
    LeanclrEngineError error{};
    if (!check(leanclr_engine_start(&config, &session_, &error), error))
        return;
    if (!attach_buffers())
    {
        UtilityFunctions::push_error(error_);
        leanclr_engine_stop(session_, &error);
        return;
    }
    ready_ = true;
    step_game(0.0, 0, -1, false);
    if (ready_)
        UtilityFunctions::print("LEANCLR_READY buffers_v1 files=", acquired_, "/", released_);
}

void LeanCLRHost::_exit_tree()
{
    if (owner != this)
        return;
    ready_ = false;
    if (session_)
    {
        LeanclrEngineError error{};
        check(leanclr_engine_stop(session_, &error), error);
        UtilityFunctions::print("LEANCLR_STOPPED files=", acquired_, "/", released_);
    }
    owner = nullptr;
}

bool LeanCLRHost::is_runtime_ready() const
{
    return ready_;
}

String LeanCLRHost::get_last_error() const
{
    return error_;
}

void LeanCLRHost::step_game(double delta, int64_t direction, int64_t pointer_x, bool restart)
{
    if (!ready_)
        return;
    if (!std::isfinite(delta) || delta < 0.0)
    {
        error_ = "Invalid frame delta";
        ready_ = false;
        return;
    }
    input_[1] = restart ? 1 : 0;
    input_[2] = static_cast<int32_t>(std::clamp<int64_t>(direction, -1, 1));
    input_[3] = static_cast<int32_t>(std::clamp<int64_t>(pointer_x, -1, 960));
    LeanclrEngineError error{};
    if (!check(leanclr_engine_tick(session_, static_cast<float>(std::min(delta, 0.1)), &error), error))
        return;
    if (output_[0] != magic || output_[1] != 1 || output_[2] < 0 || output_[2] > 64)
    {
        error_ = "Invalid managed snapshot header";
        ready_ = false;
    }
}

PackedInt32Array LeanCLRHost::get_snapshot() const
{
    PackedInt32Array result;
    if (ready_)
    {
        const int count = 16 + output_[2] * 3;
        result.resize(count);
        std::copy_n(output_.data(), count, result.ptrw());
    }
    return result;
}

void LeanCLRHost::_bind_methods()
{
    ClassDB::bind_method(D_METHOD("is_runtime_ready"), &LeanCLRHost::is_runtime_ready);
    ClassDB::bind_method(D_METHOD("get_last_error"), &LeanCLRHost::get_last_error);
    ClassDB::bind_method(D_METHOD("step_game", "delta", "direction", "pointer_x", "restart"), &LeanCLRHost::step_game);
    ClassDB::bind_method(D_METHOD("get_snapshot"), &LeanCLRHost::get_snapshot);
}
} // namespace godot

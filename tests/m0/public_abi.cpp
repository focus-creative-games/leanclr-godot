#include "engine_host.h"
#include "leanclr.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

namespace
{
std::string managed_directory, runtime_directory;
size_t acquired = 0, released = 0;
const LeanclrMethodInfo *leaf_method = nullptr, *throw_method = nullptr;

void check(bool condition, const char* name)
{
    if (!condition)
    {
        std::fprintf(stderr, "M0_ABI_FAIL %s\n", name);
        std::exit(1);
    }
    std::printf("M0_ABI_PASS %s\n", name);
}

int32_t load(void*, const char* name, const char* extension, LeanclrEngineFile* output)
{
    for (const auto& directory : {managed_directory, runtime_directory})
    {
        std::ifstream file(directory + "/" + name + "." + extension, std::ios::binary | std::ios::ate);
        if (!file)
            continue;
        auto length = file.tellg();
        if (length <= 0 || length > 64 * 1024 * 1024)
            return -1;
        auto* bytes = new std::vector<uint8_t>(static_cast<size_t>(length));
        file.seekg(0);
        if (!file.read(reinterpret_cast<char*>(bytes->data()), length))
        {
            delete bytes;
            return -1;
        }
        *output = {bytes->data(), bytes->size(), bytes};
        ++acquired;
        return 1;
    }
    return 0;
}

void release(void*, LeanclrEngineFile* file)
{
    delete static_cast<std::vector<uint8_t>*>(file->token);
    ++released;
}

uint64_t thread_id(void*)
{
    return 1; // This probe is strictly single threaded.
}

const LeanclrMethodInfo* find(LeanclrClass* klass, const char* name)
{
    LeanclrException* exception = nullptr;
    const auto* method = leanclr_get_class_method_by_name(klass, name, &exception);
    check(method && !exception, name);
    return method;
}

void native_step(LeanclrMethodPointer, const LeanclrMethodInfo*, const LeanclrStackObject* args, LeanclrStackObject* ret, LeanclrException** exception)
{
    size_t offset = 0;
    int32_t value;
    leanclr_get_argument(args, &offset, &value, sizeof(value));
    alignas(8) uint64_t argument[1]{}, result[1]{};
    auto* buffer = reinterpret_cast<LeanclrStackObject*>(argument);
    auto* output = reinterpret_cast<LeanclrStackObject*>(result);
    int32_t input = value < 0 ? 0 : value;
    offset = 0;
    leanclr_push_argument(buffer, &offset, &input, sizeof(input));
    check(exception && !*exception, "callback-exception-initialized");
    if (value == 6)
    {
        argument[0] = 0;
        leanclr_invoke_with_buffer(throw_method, buffer, output, exception);
        check(*exception != nullptr, "inner-exception-observed");
        argument[0] = 6;
    }
    leanclr_invoke_with_buffer(value < 0 ? throw_method : leaf_method, buffer, output, exception);
    if (*exception)
        return;
    int32_t answer;
    leanclr_get_return_value(output, &answer, sizeof(answer));
    ++answer;
    leanclr_set_return_value(ret, &answer, sizeof(answer));
}
} // namespace

int main(int argc, char** argv)
{
    if (argc < 3 || argc > 4)
        return 2;
    managed_directory = argv[1];
    runtime_directory = argv[2];
    const bool test_invoker = argc == 4 && std::strcmp(argv[3], "--callbacks") == 0;
    if (test_invoker)
        leanclr_register_pinvoke_func("[M0.Contracts]M0.Contracts::NativeStep", nullptr, native_step);
    LeanclrEngineConfig config{};
    config.size = sizeof(config);
    config.abi_version = LEANCLR_ENGINE_ABI_VERSION;
    config.load_file = load;
    config.release_file = release;
    config.current_thread_id = thread_id;
    config.assembly_name = "M0.Contracts";
    config.entry_type = "M0.Contracts";
    LeanclrEngineSession* session = nullptr;
    LeanclrEngineError error{};
    check(leanclr_engine_start(&config, &session, &error) == LEANCLR_ENGINE_OK, "engine-start");
    auto* assembly = leanclr_get_assembly("M0.Contracts");
    auto* module = leanclr_get_module_by_assembly(assembly);
    LeanclrException* exception = nullptr;
    auto* klass = leanclr_get_class_by_name(module, "M0.Contracts", false, &exception);
    check(klass && !exception, "class");
    const auto* scalar = find(klass, "Scalar");
    const auto* structure = find(klass, "Structure");
    throw_method = find(klass, "Throw");
    leaf_method = find(klass, "Leaf");
    alignas(8) uint64_t arguments[2]{}, results[2]{};
    auto* args = reinterpret_cast<LeanclrStackObject*>(arguments);
    auto* ret = reinterpret_cast<LeanclrStackObject*>(results);
    size_t offset = 0;
    int32_t a = 123, b = 456, value = 0;
    check(leanclr_get_total_arg_stack_object_size(scalar) == 2 && leanclr_get_return_value_stack_object_size(scalar) == 1, "scalar-layout");
    leanclr_push_argument(args, &offset, &a, sizeof(a));
    leanclr_push_argument(args, &offset, &b, sizeof(b));
    leanclr_invoke_with_buffer(scalar, args, ret, &exception);
    leanclr_get_return_value(ret, &value, sizeof(value));
    check(!exception && value == 579, "scalar-value");

    struct Pair
    {
        int32_t x;
        float y;
    } pair{7, 1.5f};

    offset = 0;
    leanclr_push_argument(args, &offset, &pair, sizeof(pair));
    leanclr_invoke_with_buffer(structure, args, ret, &exception);
    leanclr_get_return_value(ret, &pair, sizeof(pair));
    check(!exception && pair.x == 10 && pair.y == 3, "blittable-struct");
    arguments[0] = 0;
    leanclr_invoke_with_buffer(throw_method, args, ret, &exception);
    check(exception != nullptr, "managed-exception");
    // Do not dereference the borrowed exception after another managed call.
    arguments[0] = 123;
    leanclr_invoke_with_buffer(scalar, args, ret, &exception);
    const bool cleared = exception == nullptr;
    std::printf("M0_ABI_%s exception-output-cleared\n", cleared ? "PASS" : "BLOCKED");
    leanclr_invoke_with_buffer(nullptr, nullptr, nullptr, &exception);
    check(exception != nullptr, "reject-null-method");
    leanclr_invoke_with_buffer(scalar, nullptr, ret, &exception);
    check(exception != nullptr, "reject-null-arguments");
    leanclr_invoke_with_buffer(scalar, args, nullptr, &exception);
    check(exception != nullptr, "reject-null-return-buffer");
    leanclr_invoke_with_buffer(scalar, args, ret, nullptr);
    leanclr_get_return_value(ret, &value, sizeof(value));
    check(value == 579, "optional-exception-output");
    if (test_invoker)
    {
        check(cleared, "invoker-prerequisite");
        exception = nullptr;
        leanclr_invoke_with_buffer(find(klass, "Nested"), nullptr, ret, &exception);
        leanclr_get_return_value(ret, &value, sizeof(value));
        check(!exception && value == 52, "synchronous-native-managed-GC-nesting");
        leanclr_invoke_with_buffer(find(klass, "NestedDeep"), nullptr, ret, &exception);
        leanclr_get_return_value(ret, &value, sizeof(value));
        check(!exception && value == 217, "five-level-synchronous-nesting");
        leanclr_invoke_with_buffer(find(klass, "NestedRecovery"), nullptr, ret, &exception);
        leanclr_get_return_value(ret, &value, sizeof(value));
        check(!exception && value == 13, "inner-exception-recovery");
        leanclr_invoke_with_buffer(find(klass, "CatchNative"), nullptr, ret, &exception);
        leanclr_get_return_value(ret, &value, sizeof(value));
        check(!exception && value == 19, "native-exception-propagation");
        for (int iteration = 0; iteration < 64; ++iteration)
        {
            leanclr_invoke_with_buffer(find(klass, "Nested"), nullptr, ret, &exception);
            leanclr_get_return_value(ret, &value, sizeof(value));
            if (exception || value != 52)
                check(false, "repeated-GC-root-survival");
        }
        check(true, "repeated-GC-root-survival");
    }
    else
        std::puts("M0_ABI_BLOCKED callback checks were not enabled");
    check(leanclr_engine_stop(session, &error) == LEANCLR_ENGINE_OK, "engine-stop");
    check(acquired == released, "assembly-buffer-ownership");
    return cleared && test_invoker ? 0 : 3;
}

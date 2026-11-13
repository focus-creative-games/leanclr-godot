#ifdef LEANCLR_GODOT
#include "leanclr_backend.h"

#include "engine_host.h"
#include "glue/runtime_interop.h"
#include "leanclr.h"
#include "mono_gd/gd_mono_cache.h"

#include "core/io/file_access.h"
#include "core/os/os.h"
#include "core/os/thread.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <type_traits>

extern "C" const void *leanclr_godot_m1_modules();
extern "C" void leanclr_godot_aot_report();

namespace leanclr_godot {
namespace {
LeanclrEngineSession *session = nullptr;
uint64_t owner_thread = 0;
std::array<const LeanclrMethodInfo *, 37> methods{};
std::array<const char *, 37> method_names{};
const LeanclrMethodInfo *report_exception = nullptr;

[[noreturn]] void fail(const char *method, LeanclrException *exception = nullptr) {
	print_line(String("LEANCLR_GODOT_FATAL managed boundary failed: ") + method);
	if (exception && report_exception) {
		uint64_t slots[3]{};
		char16_t text[1024]{};
		char16_t *buffer = text;
		int32_t capacity = 1024;
		size_t offset = 0;
		auto *args = reinterpret_cast<LeanclrStackObject *>(slots);
		leanclr_push_argument(args, &offset, &exception, sizeof(exception));
		leanclr_push_argument(args, &offset, &buffer, sizeof(buffer));
		leanclr_push_argument(args, &offset, &capacity, sizeof(capacity));
		LeanclrException *report_error = nullptr;
		leanclr_invoke_with_buffer(report_exception, args, nullptr, &report_error);
		print_line(String("LEANCLR_MANAGED_EXCEPTION ") + String::utf16(text));
	}
	std::fprintf(stderr, "LEANCLR_GODOT_FATAL managed boundary failed: %s\n", method);
	std::fflush(stderr);
	// Static destruction would call Godot callbacks after VM caches are gone.
	std::_Exit(1);
}

int32_t load_file(void *, const char *name, const char *extension, LeanclrEngineFile *out) {
	String assembly = String::utf8(name);
	if (String(extension) != "dll" || assembly.contains("/") || assembly.contains("\\") || assembly.contains("..")) {
		return 0;
	}
	String path = "res://.leanclr/" + assembly + ".dll.bytes";
	if (!FileAccess::exists(path)) {
		return 0;
	}
	Ref<FileAccess> file = FileAccess::open(path, FileAccess::READ);
	if (file.is_null() || file->get_length() == 0 || file->get_length() > 64 * 1024 * 1024) {
		return -1;
	}
	auto *bytes = memnew(Vector<uint8_t>(file->get_buffer(file->get_length())));
	*out = { bytes->ptr(), static_cast<size_t>(bytes->size()), bytes };
	return 1;
}

void release_file(void *, LeanclrEngineFile *file) {
	memdelete(static_cast<Vector<uint8_t> *>(file->token));
}

uint64_t thread_id(void *) {
	return static_cast<uint64_t>(Thread::get_caller_id());
}

template <size_t Index, typename Function>
struct Callback;

template <size_t Index, typename R, typename... A>
struct Callback<Index, R(GD_CLR_STDCALL *)(A...)> {
	static R GD_CLR_STDCALL invoke(A... arguments) {
		if (thread_id(nullptr) != owner_thread) {
			fail("owner-thread contract");
		}
		static_assert(((sizeof(A) <= 8) && ...), "M1 callbacks accept scalar/pointer arguments only");
		std::array<uint64_t, sizeof...(A) + 1> slots{};
		uint64_t result = 0;
		size_t offset = 0;
		auto *args = reinterpret_cast<LeanclrStackObject *>(slots.data());
		(leanclr_push_argument(args, &offset, &arguments, sizeof(A)), ...);
		LeanclrException *exception = nullptr;
		leanclr_invoke_with_buffer(methods[Index], args, reinterpret_cast<LeanclrStackObject *>(&result), &exception);
		if (exception) {
			fail(method_names[Index], exception);
		}
		if constexpr (!std::is_void_v<R>) {
			static_assert(sizeof(R) <= 8);
			R value{};
			leanclr_get_return_value(reinterpret_cast<LeanclrStackObject *>(&result), &value, sizeof(R));
			return value;
		}
	}
};

bool bind(size_t index, LeanclrModuleDef *module, const char *type, const char *name, size_t args) {
	LeanclrException *exception = nullptr;
	auto *klass = leanclr_get_class_by_name(module, type, false, &exception);
	const auto *method = klass && !exception ? leanclr_get_class_method_by_name(klass, name, &exception) : nullptr;
	if (!method || exception || leanclr_get_total_arg_stack_object_size(method) != args || leanclr_get_return_value_stack_object_size(method) > 1) {
		std::fprintf(stderr, "LEANCLR_GODOT_BIND_FAILED %s::%s\n", type, name);
		return false;
	}
	methods[index] = method;
	method_names[index] = name;
	return true;
}

#include "leanclr_backend_callbacks.inc"
} // namespace

bool initialize() {
	owner_thread = thread_id(nullptr);
	LeanclrEngineConfig config{};
	config.size = sizeof(config);
	config.abi_version = LEANCLR_ENGINE_ABI_VERSION;
	config.load_file = load_file;
	config.release_file = release_file;
	config.current_thread_id = thread_id;
	config.assembly_name = "LeanClr.Bootstrap";
	config.entry_type = "LeanClr.Bootstrap";
	config.aot_modules = leanclr_godot_m1_modules();
	LeanclrEngineError error{};
	if (leanclr_engine_start(&config, &session, &error) != LEANCLR_ENGINE_OK) {
		std::fprintf(stderr, "LEANCLR_GODOT_START_FAILED %s\n", error.message);
		return false;
	}
	LeanclrException *exception = nullptr;
	auto *assembly = leanclr_load_assembly("GodotSharp", &exception);
	if (!assembly || exception) {
		return false;
	}
	GDMonoCache::ManagedCallbacks callbacks{};
	if (!bind_callbacks(leanclr_get_module_by_assembly(assembly), callbacks)) {
		return false;
	}
	GDMonoCache::update_godot_api_cache(callbacks);
	auto *bootstrap = leanclr_get_assembly("LeanClr.Bootstrap");
	auto *klass = leanclr_get_class_by_name(leanclr_get_module_by_assembly(bootstrap), "LeanClr.Bootstrap", false, &exception);
	report_exception = klass ? leanclr_get_class_method_by_name(klass, "ReportException", &exception) : nullptr;
	const auto *attach = klass ? leanclr_get_class_method_by_name(klass, "Attach", &exception) : nullptr;
	if (!attach || exception) {
		return false;
	}
	int32_t size = 0;
	const void **table = godotsharp::get_runtime_interop_funcs(size);
	uint64_t slots[2]{};
	auto *args = reinterpret_cast<LeanclrStackObject *>(slots);
	size_t offset = 0;
	leanclr_push_argument(args, &offset, &table, sizeof(table));
	leanclr_push_argument(args, &offset, &size, sizeof(size));
	leanclr_invoke_with_buffer(attach, args, nullptr, &exception);
	if (exception) {
		fail("Bootstrap.Attach");
	}
	GDMonoCache::managed_callbacks.GD_OnCoreApiAssemblyLoaded(false);
	print_line("LEANCLR_GODOT_READY backend=LeanCLR script_language=CSharpScript");
	return true;
}

void shutdown() {
	if (session) {
		LeanclrEngineError error{};
		leanclr_engine_stop(session, &error);
		leanclr_godot_aot_report();
		session = nullptr;
	}
}
} // namespace leanclr_godot
#endif

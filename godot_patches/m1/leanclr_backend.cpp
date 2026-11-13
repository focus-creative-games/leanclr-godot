#ifdef LEANCLR_GODOT
#include "leanclr_backend.h"

#include "engine_host.h"
#include "glue/runtime_interop.h"
#include "leanclr.h"
#include "mono_gd/gd_mono_cache.h"

#include "core/crypto/crypto_core.h"
#include "core/io/file_access.h"
#include "core/io/json.h"
#include "core/os/os.h"
#include "core/os/thread.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <type_traits>
#ifdef WEB_ENABLED
#include <emscripten/heap.h>
#endif

extern "C" const void *leanclr_godot_m1_modules();
extern "C" bool leanclr_godot_aot_counters(uint64_t *steps, uint64_t *benchmarks);
extern "C" const char *leanclr_godot_contract(unsigned index);
extern "C" const char *leanclr_godot_aot_assembly_sha256();
extern "C" void leanclr_godot_aot_marker(uint64_t steps, uint64_t benchmarks) {
	print_line("LEANCLR_AOT_HOTCALL module=DemoLogic step=" + uitos(steps) + " benchmark=" + uitos(benchmarks));
}

namespace leanclr_godot {
static_assert(sizeof(real_t) == 4, "The validated GodotSharp publication ABI requires single precision.");
namespace {
LeanclrEngineSession *session = nullptr;
uint64_t owner_thread = 0;
std::array<const LeanclrMethodInfo *, 37> methods{};
std::array<const char *, 37> method_names{};
const LeanclrMethodInfo *report_exception = nullptr;
Dictionary payload_hashes;

bool validate_payload() {
	const String manifest_path = "res://.leanclr/manifest.json";
	Ref<FileAccess> manifest_file = FileAccess::open(manifest_path, FileAccess::READ);
	if (manifest_file.is_null() || manifest_file->get_length() > 512 * 1024) {
		return false;
	}
	Variant parsed = JSON::parse_string(manifest_file->get_as_text());
	if (parsed.get_type() != Variant::DICTIONARY) {
		return false;
	}
	Dictionary manifest = parsed;
	if (String(manifest.get("godot_commit", "")) != leanclr_godot_contract(0) ||
			String(manifest.get("leanclr_commit", "")) != leanclr_godot_contract(1) ||
			String(manifest.get("calli_sha256", "")) != leanclr_godot_contract(5) ||
			int64_t(manifest.get("pointer_bits", 0)) != sizeof(void *) * 8 ||
			int64_t(manifest.get("real_bits", 0)) != 32) {
		return false;
	}
	Array files = manifest.get("files", Array());
	if (files.is_empty() || files.size() > 256) {
		return false;
	}
	for (const Variant &item : files) {
		if (item.get_type() != Variant::DICTIONARY) {
			return false;
		}
		Dictionary entry = item;
		String source = entry.get("source", "");
		String hash = entry.get("sha256", "");
		if (source.is_empty() || source.contains("/") || source.contains("\\") || source.contains("..") || hash.length() != 64 || payload_hashes.has(source)) {
			return false;
		}
		payload_hashes[source] = hash;
	}
	const String aot_hash = leanclr_godot_aot_assembly_sha256();
	if (!aot_hash.is_empty() && String(payload_hashes.get("DemoLogic.dll.bytes", "")) != aot_hash) {
		return false;
	}
#ifdef WEB_ENABLED
	const unsigned corelib_contract = 4;
#else
	const unsigned corelib_contract = 3;
#endif
	return String(payload_hashes.get("GodotSharp.dll.bytes", "")) == leanclr_godot_contract(2) &&
			String(payload_hashes.get("System.Private.CoreLib.dll.bytes", "")) == leanclr_godot_contract(corelib_contract);
}

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
	uint8_t digest[32];
	if (CryptoCore::sha256(bytes->ptr(), bytes->size(), digest) != OK ||
			String(payload_hashes.get(assembly + ".dll.bytes", "")) != String::hex_encode_buffer(digest, 32)) {
		memdelete(bytes);
		return -1;
	}
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
	if (!validate_payload()) {
		print_line("LEANCLR_PUBLICATION_REJECTED template, bindings, ABI or CoreLib mismatch");
		std::_Exit(78);
	}
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
		print_line(String("LEANCLR_GODOT_START_FAILED ") + error.message);
		std::_Exit(78);
	}
	LeanclrException *exception = nullptr;
	auto *assembly = leanclr_load_assembly("GodotSharp", &exception);
	if (!assembly || exception) {
		fail("load GodotSharp", exception);
	}
	GDMonoCache::ManagedCallbacks callbacks{};
	if (!bind_callbacks(leanclr_get_module_by_assembly(assembly), callbacks)) {
		fail("bind GodotSharp callbacks");
	}
	GDMonoCache::update_godot_api_cache(callbacks);
	auto *bootstrap = leanclr_get_assembly("LeanClr.Bootstrap");
	auto *klass = leanclr_get_class_by_name(leanclr_get_module_by_assembly(bootstrap), "LeanClr.Bootstrap", false, &exception);
	report_exception = klass ? leanclr_get_class_method_by_name(klass, "ReportException", &exception) : nullptr;
	const auto *attach = klass ? leanclr_get_class_method_by_name(klass, "Attach", &exception) : nullptr;
	if (!attach || exception) {
		fail("find Bootstrap.Attach", exception);
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
		fail("Bootstrap.Attach", exception);
	}
	GDMonoCache::managed_callbacks.GD_OnCoreApiAssemblyLoaded(false);
	print_line("LEANCLR_GODOT_READY backend=LeanCLR script_language=CSharpScript");
	return true;
}

void shutdown() {
	if (session) {
#ifdef WEB_ENABLED
		print_line("LEANCLR_WASM_MEMORY bytes=" + itos(emscripten_get_heap_size()));
#endif
		LeanclrEngineError error{};
		leanclr_engine_stop(session, &error);
		uint64_t steps = 0;
		uint64_t benchmarks = 0;
		if (leanclr_godot_aot_counters(&steps, &benchmarks)) {
			print_line("LEANCLR_AOT_EXECUTED module=DemoLogic step=" + uitos(steps) + " benchmark=" + uitos(benchmarks));
		}
		session = nullptr;
	}
}
} // namespace leanclr_godot
#endif

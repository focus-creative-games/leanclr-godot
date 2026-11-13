#include "leanclr_host.h"
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/godot.hpp>

static void initialize(godot::ModuleInitializationLevel level)
{
    if (level == godot::MODULE_INITIALIZATION_LEVEL_SCENE)
        GDREGISTER_CLASS(godot::LeanCLRHost);
}

extern "C" GDExtensionBool GDE_EXPORT leanclr_godot_library_init(GDExtensionInterfaceGetProcAddress get_proc_address, GDExtensionClassLibraryPtr library,
                                                                 GDExtensionInitialization* initialization)
{
    godot::GDExtensionBinding::InitObject init(get_proc_address, library, initialization);
    init.register_initializer(initialize);
    init.set_minimum_library_initialization_level(godot::MODULE_INITIALIZATION_LEVEL_SCENE);
    return init.init();
}

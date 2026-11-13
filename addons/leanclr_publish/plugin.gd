@tool
extends EditorPlugin

const TARGETS = ["win64", "html5", "android"]

func _enter_tree() -> void:
	for target in TARGETS:
		add_tool_menu_item("LeanCLR: Publish " + target, _publish.bind(target))
	print("LEANCLR_EDITOR_PUBLISH_MENU_READY targets=win64,html5,android")

func _exit_tree() -> void:
	for target in TARGETS:
		remove_tool_menu_item("LeanCLR: Publish " + target)

func _publish(target: String) -> void:
	var project = ProjectSettings.globalize_path("res://")
	# The SDK checkout is two directories above the bundled sample projects.
	var sdk = project.path_join("../..").simplify_path()
	var script = sdk.path_join("tools/publish.py")
	if not FileAccess.file_exists(script):
		push_error("Place this addon in a bundled SDK sample project, or run tools/publish.py with an explicit project path.")
		return
	var destination = sdk.path_join("build/export/editor-%s-%s" % [target, Time.get_unix_time_from_system()])
	var pid = OS.create_process("python", PackedStringArray([script, "--target", target, "--sample", project, "--output", destination]))
	if pid < 0:
		push_error("Could not start Python. Run tools/publish.py from the SDK command line.")
	else:
		print("LeanCLR publishing process ", pid, "; output or staging diagnostics: ", destination)

extends SceneTree

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		quit(2)
		return
	var manifest = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not ProjectSettings.load_resource_pack(args[1]):
		quit(1)
		return
	for entry in manifest.files:
		if FileAccess.get_sha256(entry.path) != entry.sha256:
			push_error("M0 export payload mismatch: " + entry.path)
			quit(1)
			return
	if FileAccess.get_file_as_string("res://Player.cs") != "\n":
		push_error("M0 exported script placeholder mismatch")
		quit(1)
		return
	var scene = load("res://Main.tscn") as PackedScene
	if scene == null:
		quit(1)
		return
	var node := scene.instantiate()
	var script: Script = node.get_script()
	if script == null or script.get_class() != "CSharpScript" or script.resource_path != "res://Player.cs" or node.get("Speed") != 120.0:
		push_error("M0 scene-to-C# mapping mismatch")
		node.free()
		quit(1)
		return
	node.free()
	print("M0_EXPORT_VERIFY_OK target=" + manifest.target + " script=res://Player.cs")
	quit()

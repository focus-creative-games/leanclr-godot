extends SceneTree

# M0 only: verify script identities and managed payloads can share a PCK.
# This is a container probe, not a runnable LeanCLR C# export template.
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 3:
		quit(2)
		return
	var stage := args[0]
	var manifest_path := stage.path_join("manifest.json")
	var manifest = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	if not manifest is Dictionary or manifest.get("runtime_ready", true) != false:
		quit(2)
		return
	if args[2] == "pack":
		var packer := PCKPacker.new()
		if packer.pck_start(args[1]) != OK:
			quit(1)
			return
		for entry in manifest.files:
			if packer.add_file(entry.path, stage.path_join(entry.source)) != OK:
				quit(1)
				return
		if packer.flush() != OK:
			quit(1)
			return
	elif args[2] == "verify":
		if not ProjectSettings.load_resource_pack(args[1]):
			quit(1)
			return
		for entry in manifest.files:
			if FileAccess.get_sha256(entry.path) != entry.sha256:
				push_error("M0 PCK mismatch: " + entry.path)
				quit(1)
				return
	else:
		quit(2)
		return
	print("M0_PCK_OK mode=" + args[2] + " target=" + manifest.target)
	quit()

extends Control

@onready var runtime: LeanCLRHost = $Runtime
var state := PackedInt32Array()
var pointer_x := -1
var restart := false
var has_started := false
var smoke := false
var smoke_frames := 0
var clock := 0.0
var title: Label
var stats: Label
var status: Label
var button: Button

func _ready() -> void:
	Engine.max_fps = 60
	smoke = "--smoke-test" in OS.get_cmdline_user_args()
	title = Label.new()
	title.text = "LEANCLR  /  FLIGHT"
	title.position = Vector2(32, 20)
	title.add_theme_font_size_override("font_size", 30)
	add_child(title)
	stats = Label.new()
	stats.position = Vector2(32, 65)
	stats.add_theme_font_size_override("font_size", 19)
	add_child(stats)
	status = Label.new()
	status.position = Vector2(32, 603)
	status.text = "C# gameplay  /  Godot presentation  /  arrows, A-D or drag to move"
	add_child(status)
	button = Button.new()
	button.text = "START FLIGHT"
	button.position = Vector2(380, 320)
	button.size = Vector2(200, 55)
	button.pressed.connect(func(): restart = true)
	add_child(button)
	if not runtime.is_runtime_ready():
		status.text = runtime.get_last_error()
		button.disabled = true
		if smoke:
			get_tree().quit(1)
		return
	state = runtime.get_snapshot()
	if smoke:
		restart = true

func _process(delta: float) -> void:
	if not runtime.is_runtime_ready():
		return
	clock += delta
	var direction := int(Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT))
	direction -= int(Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT))
	if smoke:
		delta = 1.0 / 60.0
		direction = 1
	if restart:
		has_started = true
	runtime.step_game(delta, direction, pointer_x, restart)
	restart = false
	if not runtime.is_runtime_ready():
		status.text = runtime.get_last_error()
		if smoke:
			get_tree().quit(1)
		return
	state = runtime.get_snapshot()
	stats.text = "SCORE %04d     LIVES %d     COMBO x%d     TIME %02d     WAVE %d" % [state[3], state[4], state[5], int(ceil(state[6] / 1000.0)), state[7]]
	button.visible = state[10] == 0
	button.text = "FLY AGAIN" if has_started else "START FLIGHT"
	queue_redraw()
	if smoke:
		smoke_frames += 1
		if smoke_frames == 120:
			if state[11] != 121 or state[8] != 942 or state[6] >= 59000 or state[2] == 0:
				push_error("SMOKE_FAILED " + str(state))
				get_tree().quit(2)
			else:
				print("LEANCLR_SMOKE_OK ticks=", state[11], " x=", state[8], " entities=", state[2], " remaining=", state[6])
				for arg in OS.get_cmdline_user_args():
					if arg.begins_with("--capture="):
						await RenderingServer.frame_post_draw
						var capture_error := get_viewport().get_texture().get_image().save_png(arg.trim_prefix("--capture="))
						if capture_error != OK:
							get_tree().quit(3)
							return
				get_tree().quit()

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		pointer_x = int(event.position.x) if event.pressed else -1
	elif event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		pointer_x = int(event.position.x)
	elif event is InputEventScreenTouch:
		pointer_x = int(event.position.x) if event.pressed else -1
	elif event is InputEventScreenDrag:
		pointer_x = int(event.position.x)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_SPACE:
		restart = true

func _draw() -> void:
	draw_rect(Rect2(24, 110, 912, 480), Color("101f33"))
	for x in range(32, 936, 48):
		draw_line(Vector2(x, 110), Vector2(x, 590), Color(0.3, 0.6, 0.8, 0.1))
	for i in range(40):
		var x := float((i * 137 + 23) % 900 + 30)
		var y := fmod(float(i * 73) + clock * 18, 470.0) + 115
		draw_circle(Vector2(x, y), 1.5, Color(0.4, 0.7, 0.9, 0.4))
	if state.is_empty():
		return
	for i in range(state[2]):
		var offset := 16 + i * 3
		var p := Vector2(state[offset + 1], state[offset + 2])
		if state[offset] == 0:
			draw_circle(p, 20, Color(1, 0.8, 0.3, 0.12))
			draw_circle(p, 10, Color("ffd46d"))
			draw_line(p - Vector2(15, 0), p + Vector2(15, 0), Color("fff2bb"), 2)
			draw_line(p - Vector2(0, 15), p + Vector2(0, 15), Color("fff2bb"), 2)
		else:
			draw_circle(p, 19, Color("9d3c51"))
			draw_arc(p, 19, 0, TAU, 20, Color("ff6c7f"), 2)
	var player := Vector2(state[8], 550)
	var alpha := 0.4 if state[9] > 0 and int(clock * 15) % 2 == 0 else 1.0
	draw_colored_polygon(PackedVector2Array([player + Vector2(0, -23), player + Vector2(18, 18), player + Vector2(0, 10), player + Vector2(-18, 18)]), Color(0.8, 0.95, 1, alpha))
	draw_colored_polygon(PackedVector2Array([player + Vector2(-6, 18), player + Vector2(0, 30 + sin(clock * 25) * 5), player + Vector2(6, 18)]), Color("6cdef5"))

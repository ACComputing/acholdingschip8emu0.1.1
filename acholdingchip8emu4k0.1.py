import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import random
import threading
import time
import os

# --- CHIP-8 CPU Core ---
class Chip8:
    def __init__(self):
        self.memory = bytearray(4096)
        self.V = bytearray(16)
        self.I = 0
        self.pc = 0x200
        self.stack = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = [0] * (64 * 32)
        self.keys = [0] * 16
        self.draw_flag = False
        self.halted = True
        self.speed = 10  # Instructions per frame
        self.cycles = 0

        # Standard CHIP-8 font set
        self.fonts = [
            0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
            0x20, 0x60, 0x20, 0x20, 0x70, # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
            0x90, 0x90, 0xF0, 0x10, 0x10, # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
            0xF0, 0x10, 0x20, 0x40, 0x40, # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90, # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
            0xF0, 0x80, 0x80, 0x80, 0xF0, # C
            0xE0, 0x90, 0x90, 0x90, 0xE0, # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
            0xF0, 0x80, 0xF0, 0x80, 0x80  # F
        ]
        self.reset()

    def reset(self):
        self.memory = bytearray(4096)
        self.memory[0x50:0x50+len(self.fonts)] = self.fonts
        self.V = bytearray(16)
        self.I = 0
        self.pc = 0x200
        self.stack = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = [0] * (64 * 32)
        self.keys = [0] * 16
        self.draw_flag = True
        self.halted = True
        self.cycles = 0

    def load_rom(self, rom_path):
        self.reset()
        try:
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
                for i, byte in enumerate(rom_data):
                    if 0x200 + i < 4096:
                        self.memory[0x200 + i] = byte
            self.halted = False
            return True
        except Exception as e:
            return False

    def emulate_cycle(self):
        if self.halted: return
        self.cycles += 1

        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2

        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        nnn = opcode & 0x0FFF
        kk = opcode & 0x00FF
        n = opcode & 0x000F

        if opcode == 0x00E0: # CLS
            self.display = [0] * (64 * 32)
            self.draw_flag = True
        elif opcode == 0x00EE: # RET
            self.pc = self.stack.pop()
        elif (opcode & 0xF000) == 0x1000: # JP addr
            self.pc = nnn
        elif (opcode & 0xF000) == 0x2000: # CALL addr
            self.stack.append(self.pc)
            self.pc = nnn
        elif (opcode & 0xF000) == 0x3000: # SE Vx, byte
            if self.V[x] == kk: self.pc += 2
        elif (opcode & 0xF000) == 0x4000: # SNE Vx, byte
            if self.V[x] != kk: self.pc += 2
        elif (opcode & 0xF000) == 0x5000: # SE Vx, Vy
            if self.V[x] == self.V[y]: self.pc += 2
        elif (opcode & 0xF000) == 0x6000: # LD Vx, byte
            self.V[x] = kk
        elif (opcode & 0xF000) == 0x7000: # ADD Vx, byte
            self.V[x] = (self.V[x] + kk) & 0xFF
        elif (opcode & 0xF000) == 0x8000:
            if n == 0: self.V[x] = self.V[y]
            elif n == 1: self.V[x] |= self.V[y]
            elif n == 2: self.V[x] &= self.V[y]
            elif n == 3: self.V[x] ^= self.V[y]
            elif n == 4:
                res = self.V[x] + self.V[y]
                self.V[0xF] = 1 if res > 0xFF else 0
                self.V[x] = res & 0xFF
            elif n == 5:
                self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
                self.V[x] = (self.V[x] - self.V[y]) & 0xFF
            elif n == 6:
                self.V[0xF] = self.V[x] & 1
                self.V[x] >>= 1
            elif n == 7:
                self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
                self.V[x] = (self.V[y] - self.V[x]) & 0xFF
            elif n == 0xE:
                self.V[0xF] = (self.V[x] & 0x80) >> 7
                self.V[x] = (self.V[x] << 1) & 0xFF
        elif (opcode & 0xF000) == 0x9000: # SNE Vx, Vy
            if self.V[x] != self.V[y]: self.pc += 2
        elif (opcode & 0xF000) == 0xA000: # LD I, addr
            self.I = nnn
        elif (opcode & 0xF000) == 0xB000: # JP V0, addr
            self.pc = nnn + self.V[0]
        elif (opcode & 0xF000) == 0xC000: # RND Vx, byte
            self.V[x] = random.randint(0, 255) & kk
        elif (opcode & 0xF000) == 0xD000: # DRW Vx, Vy, nibble
            self.V[0xF] = 0
            for row in range(n):
                sprite_byte = self.memory[self.I + row]
                for col in range(8):
                    if (sprite_byte & (0x80 >> col)):
                        px = (self.V[x] + col) % 64
                        py = (self.V[y] + row) % 32
                        idx = px + (py * 64)
                        if self.display[idx] == 1:
                            self.V[0xF] = 1
                        self.display[idx] ^= 1
            self.draw_flag = True
        elif (opcode & 0xF000) == 0xE000:
            if kk == 0x9E: # SKP Vx
                if self.keys[self.V[x]]: self.pc += 2
            elif kk == 0xA1: # SKNP Vx
                if not self.keys[self.V[x]]: self.pc += 2
        elif (opcode & 0xF000) == 0xF000:
            if kk == 0x07: self.V[x] = self.delay_timer
            elif kk == 0x0A: # LD Vx, K
                pressed = False
                for i, k in enumerate(self.keys):
                    if k:
                        self.V[x] = i
                        pressed = True
                        break
                if not pressed: self.pc -= 2
            elif kk == 0x15: self.delay_timer = self.V[x]
            elif kk == 0x18: self.sound_timer = self.V[x]
            elif kk == 0x1E: self.I = (self.I + self.V[x]) & 0xFFFF
            elif kk == 0x29: self.I = 0x50 + (self.V[x] * 5)
            elif kk == 0x33:
                self.memory[self.I] = self.V[x] // 100
                self.memory[self.I + 1] = (self.V[x] // 10) % 10
                self.memory[self.I + 2] = self.V[x] % 10
            elif kk == 0x55:
                for i in range(x + 1): self.memory[self.I + i] = self.V[i]
            elif kk == 0x65:
                for i in range(x + 1): self.V[i] = self.memory[self.I + i]

    def update_timers(self):
        if self.delay_timer > 0: self.delay_timer -= 1
        if self.sound_timer > 0: self.sound_timer -= 1

# --- Tkinter GUI Interface ---
class Chip8GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AC'S chip 8 emu 0.1")
        self.root.geometry("850x450")
        self.root.resizable(False, False)
        
        # Apply a classic Windows-like theme if available
        style = ttk.Style()
        if 'winnative' in style.theme_names():
            style.theme_use('winnative')
        elif 'classic' in style.theme_names():
            style.theme_use('classic')

        self.cpu = Chip8()
        self.after_id = None
        self.last_time = time.time()
        self.cycles_this_sec = 0
        self.fps_rate = 60

        # Mapping PC keys to CHIP-8 hex pad
        self.key_map = {
            '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
            'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
            'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
            'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
        }

        self.build_ui()
        self.setup_bindings()
        self.loop()

    def build_ui(self):
        # Menu Bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        for menu_name in ["File", "Emulation", "Config", "Tools", "View", "Help"]:
            menubar.add_cascade(label=menu_name, menu=tk.Menu(menubar, tearoff=0))

        # Top Frame (ROM and Toolbar)
        top_container = tk.Frame(self.root)
        top_container.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

        # ROM Selection Line
        rom_frame = tk.Frame(top_container)
        rom_frame.pack(side=tk.TOP, fill=tk.X)
        tk.Label(rom_frame, text="ROM:").pack(side=tk.LEFT)
        self.rom_combo = ttk.Combobox(rom_frame, values=["[None Loaded]"], state="readonly")
        self.rom_combo.current(0)
        self.rom_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(rom_frame, text="Load...", width=10, command=self.open_rom).pack(side=tk.LEFT)

        # Toolbar
        toolbar_frame = tk.Frame(top_container)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        btn_config = {'width': 10, 'relief': tk.RAISED, 'bd': 1}
        
        self.btn_open = tk.Button(toolbar_frame, text="📁\nOpen", command=self.open_rom, **btn_config)
        self.btn_open.pack(side=tk.LEFT, padx=2)
        
        self.btn_play = tk.Button(toolbar_frame, text="▶\nPlay", fg="green", command=self.play, **btn_config)
        self.btn_play.pack(side=tk.LEFT, padx=2)
        
        self.btn_pause = tk.Button(toolbar_frame, text="⏸\nPause", fg="blue", command=self.pause, **btn_config)
        self.btn_pause.pack(side=tk.LEFT, padx=2)
        
        self.btn_reset = tk.Button(toolbar_frame, text="🔄\nReset", fg="green", command=self.reset, **btn_config)
        self.btn_reset.pack(side=tk.LEFT, padx=2)
        
        self.btn_frame = tk.Button(toolbar_frame, text="⏭\nFrame Advance", fg="blue", command=self.frame_advance, **btn_config)
        self.btn_frame.pack(side=tk.LEFT, padx=2)

        self.limit_speed_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar_frame, text="Limit Speed", variable=self.limit_speed_var).pack(side=tk.LEFT, padx=10)

        # Main Layout (Screen + Sidebar)
        main_frame = tk.Frame(self.root)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Game Screen
        screen_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        screen_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(screen_frame, bg="black", width=640, height=320, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.no_rom_text = self.canvas.create_text(320, 160, text="NO ROM LOADED", fill="white", font=("Courier", 16, "bold"))

        # Right Sidebar
        sidebar = tk.Frame(main_frame, width=220)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        sidebar.pack_propagate(False)

        # Emulation State
        state_frame = tk.LabelFrame(sidebar, text="Emulation State")
        state_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        self.lbl_status = tk.Label(state_frame, text="Status:\tStopped")
        self.lbl_status.pack(anchor="w", padx=5)
        self.lbl_speed = tk.Label(state_frame, text="Speed:\t100%")
        self.lbl_speed.pack(anchor="w", padx=5)
        self.lbl_cycles = tk.Label(state_frame, text="Cycles/sec:\t0")
        self.lbl_cycles.pack(anchor="w", padx=5)

        # Registers & Memory
        reg_frame = tk.LabelFrame(sidebar, text="Registers & Memory")
        reg_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.reg_vars = {}
        reg_grid = tk.Frame(reg_frame)
        reg_grid.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)

        # Left Column (V0-V7), Right Column (V8-VF but labelled VA-VE, PC, I, DT, ST to match image style closely)
        labels_left = [f"V{i}" for i in range(8)]
        labels_right = ["VA", "VC", "VD", "VE", "PC", "I", "DT", "ST"]
        
        for i in range(8):
            # Left Col
            tk.Label(reg_grid, text=labels_left[i], font=("Courier", 9)).grid(row=i, column=0, sticky="e")
            v_left = tk.StringVar(value="00 / $00")
            self.reg_vars[labels_left[i]] = v_left
            tk.Entry(reg_grid, textvariable=v_left, width=9, state="readonly", font=("Courier", 9)).grid(row=i, column=1, padx=(0, 5))
            
            # Right Col
            tk.Label(reg_grid, text=labels_right[i], font=("Courier", 9)).grid(row=i, column=2, sticky="e")
            v_right = tk.StringVar(value="00 / $00")
            self.reg_vars[labels_right[i]] = v_right
            tk.Entry(reg_grid, textvariable=v_right, width=9, state="readonly", font=("Courier", 9)).grid(row=i, column=3)

        # RAM Monitor
        tk.Label(reg_frame, text="RAM Monitor:").pack(anchor="w", padx=2, pady=(5,0))
        ram_scroll = tk.Scrollbar(reg_frame)
        ram_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ram_text = tk.Text(reg_frame, height=5, width=20, yscrollcommand=ram_scroll.set, font=("Courier", 9))
        self.ram_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ram_scroll.config(command=self.ram_text.yview)
        
        # Populate dummy RAM data initially
        self.update_ram_monitor()

        # Bottom Buttons
        btn_frame = tk.Frame(sidebar)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        ttk.Button(btn_frame, text="Input Config", width=12).pack(side=tk.LEFT, expand=True)
        ttk.Button(btn_frame, text="Palette...", width=10).pack(side=tk.RIGHT, expand=True)

    def setup_bindings(self):
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in self.key_map:
            self.cpu.keys[self.key_map[key]] = 1

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.key_map:
            self.cpu.keys[self.key_map[key]] = 0

    def open_rom(self):
        filepath = filedialog.askopenfilename(title="Open CHIP-8 ROM", filetypes=[("CHIP-8 ROMs", "*.ch8"), ("All Files", "*.*")])
        if filepath:
            filename = os.path.basename(filepath)
            if self.cpu.load_rom(filepath):
                self.rom_combo.set(filename)
                self.canvas.delete(self.no_rom_text)
                self.lbl_status.config(text="Status:\tRunning")
                self.update_debug_info()

    def play(self):
        if self.rom_combo.get() != "[None Loaded]":
            self.cpu.halted = False
            self.lbl_status.config(text="Status:\tRunning")

    def pause(self):
        self.cpu.halted = True
        self.lbl_status.config(text="Status:\tPaused")

    def reset(self):
        if self.rom_combo.get() != "[None Loaded]":
            # Very basic reset for simulation, usually requires reloading ROM in full emulators
            self.cpu.pc = 0x200
            self.cpu.display = [0] * (64 * 32)
            self.cpu.draw_flag = True
            self.update_canvas()

    def frame_advance(self):
        was_halted = self.cpu.halted
        self.cpu.halted = False
        for _ in range(self.cpu.speed):
            self.cpu.emulate_cycle()
        self.cpu.update_timers()
        if self.cpu.draw_flag:
            self.update_canvas()
            self.cpu.draw_flag = False
        self.update_debug_info()
        self.cpu.halted = was_halted

    def update_canvas(self):
        self.canvas.delete("all")
        # Draw pixels scaling 10x for 640x320 canvas
        for y in range(32):
            for x in range(64):
                if self.cpu.display[x + (y * 64)]:
                    self.canvas.create_rectangle(x*10, y*10, x*10+10, y*10+10, fill="white", outline="")

    def update_debug_info(self):
        # Update registers dynamically
        for i in range(8):
            val = self.cpu.V[i]
            self.reg_vars[f"V{i}"].set(f"{val:02} / ${val:02X}")
        
        # Mapped right columns based on visual mockup requests
        self.reg_vars["VA"].set(f"{self.cpu.V[0xA]:02} / ${self.cpu.V[0xA]:02X}")
        self.reg_vars["VC"].set(f"{self.cpu.V[0xC]:02} / ${self.cpu.V[0xC]:02X}")
        self.reg_vars["VD"].set(f"{self.cpu.V[0xD]:02} / ${self.cpu.V[0xD]:02X}")
        self.reg_vars["VE"].set(f"{self.cpu.V[0xE]:02} / ${self.cpu.V[0xE]:02X}")
        
        self.reg_vars["PC"].set(f"{self.cpu.pc:03} / ${self.cpu.pc:03X}")
        self.reg_vars["I"].set(f"{self.cpu.I:03} / ${self.cpu.I:03X}")
        self.reg_vars["DT"].set(f"{self.cpu.delay_timer:02} / ${self.cpu.delay_timer:02X}")
        self.reg_vars["ST"].set(f"{self.cpu.sound_timer:02} / ${self.cpu.sound_timer:02X}")

        self.update_ram_monitor()

    def update_ram_monitor(self):
        self.ram_text.config(state=tk.NORMAL)
        self.ram_text.delete(1.0, tk.END)
        # Show chunk of memory around PC
        start_mem = max(0x200, self.cpu.pc - 4)
        for i in range(8):
            addr = start_mem + i
            if addr < 4096:
                val = self.cpu.memory[addr]
                # Mimic the 00000000 format seen in screenshot (binary/hex mix representation)
                bin_str = f"{val:08b}"
                self.ram_text.insert(tk.END, f"{bin_str}\n")
        self.ram_text.config(state=tk.DISABLED)

    def loop(self):
        current_time = time.time()
        
        # If running, emulate a frame (~10 instructions per 60hz frame)
        if not self.cpu.halted:
            for _ in range(self.cpu.speed):
                self.cpu.emulate_cycle()
                self.cycles_this_sec += 1
            
            self.cpu.update_timers()
            
            if self.cpu.draw_flag:
                self.update_canvas()
                self.cpu.draw_flag = False
            
            # Update debugger roughly every frame visually
            self.update_debug_info()

        # Simple FPS and cycle calculation
        if current_time - self.last_time >= 1.0:
            self.lbl_cycles.config(text=f"Cycles/sec:\t{self.cycles_this_sec}")
            self.cycles_this_sec = 0
            self.last_time = current_time

        # Schedule next loop at 60Hz (~16ms)
        delay = 16 if self.limit_speed_var.get() else 1
        self.after_id = self.root.after(delay, self.loop)


if __name__ == "__main__":
    root = tk.Tk()
    app = Chip8GUI(root)
    root.mainloop()

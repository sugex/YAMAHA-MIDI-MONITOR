import mido
import threading
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from queue import Queue, Empty


class MidiMonitorGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("MIDI Monitor FINAL PRO v7")
        self.root.geometry("1050x780")
        self.root.minsize(950, 650)

        self.running = False
        self.inport = None
        self.outport = None

        self.rx_count = 0
        self.tx_count = 0

        self.current_bpm = tk.StringVar(value="---")

        self.queue = Queue()

        self.build_ui()
        self.refresh_devices()

        self.root.after(5, self.process_queue)

    # ================= UI =================

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # ===== DARK THEME =====
        dark_bg = "#1e1e1e"
        frame_bg = "#252526"
        text_bg = "#2d2d2d"
        fg_color = "#ffffff"
        accent = "#3a96dd"

        self.root.configure(bg=dark_bg)

        style.configure(".",
                        background=dark_bg,
                        foreground=fg_color,
                        fieldbackground=text_bg)

        style.configure("TLabel",
                        background=dark_bg,
                        foreground=fg_color)

        style.configure("TFrame",
                        background=dark_bg)

        style.configure("TLabelframe",
                        background=dark_bg,
                        foreground=fg_color)

        style.configure("TLabelframe.Label",
                        background=dark_bg,
                        foreground=accent)

        style.configure("TButton",
                        background=frame_bg,
                        foreground=fg_color)

        style.map("TButton",
                  background=[("active", accent)])

        style.configure("TCheckbutton",
                        background=dark_bg,
                        foreground=fg_color)

        style.configure("TCombobox",
                        fieldbackground=text_bg,
                        background=text_bg,
                        foreground=fg_color)

        # ===== DEVICE FRAME =====
        top_frame = ttk.LabelFrame(self.root, text="MIDI Device")
        top_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(top_frame, text="MIDI IN:").grid(row=0, column=0, padx=5)
        self.in_combo = ttk.Combobox(top_frame, width=35, state="readonly")
        self.in_combo.grid(row=0, column=1, padx=5)

        ttk.Label(top_frame, text="MIDI OUT:").grid(row=0, column=2, padx=5)
        self.out_combo = ttk.Combobox(top_frame, width=35, state="readonly")
        self.out_combo.grid(row=0, column=3, padx=5)

        ttk.Button(top_frame, text="Refresh",
                   command=self.refresh_devices).grid(row=0, column=4, padx=5)
        ttk.Button(top_frame, text="Start",
                   command=self.start).grid(row=0, column=5, padx=5)
        ttk.Button(top_frame, text="Stop",
                   command=self.stop).grid(row=0, column=6, padx=5)

        self.thru_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top_frame,
            text="Enable MIDI Thru",
            variable=self.thru_enabled
        ).grid(row=1, column=1, pady=5, sticky="w")

        self.warning_label = ttk.Label(top_frame, text="", foreground="red")
        self.warning_label.grid(row=1, column=3, sticky="w")

        # ===== TEMPO =====
        tempo_frame = ttk.LabelFrame(self.root, text="TEMPO")
        tempo_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(tempo_frame, text="Current BPM:",
                  font=("Arial", 12)).pack(side="left", padx=10)

        self.tempo_label = ttk.Label(
            tempo_frame,
            textvariable=self.current_bpm,
            font=("Arial", 22, "bold"),
            foreground=accent
        )
        self.tempo_label.pack(side="left")

        # ===== FILTER =====
        filter_frame = ttk.LabelFrame(self.root, text="FILTER")
        filter_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(filter_frame, text="Channel:").grid(row=0, column=0, padx=5)

        self.channel_var = tk.StringVar()
        self.channel_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.channel_var,
            values=["All"] + [str(i) for i in range(1, 17)],
            width=5,
            state="readonly"
        )
        self.channel_combo.current(0)
        self.channel_combo.grid(row=0, column=1, padx=5)

        self.filter_vars = {}
        msg_types = [
            "note_on", "note_off", "control_change",
            "program_change", "pitchwheel",
            "aftertouch", "polytouch",
            "sysex", "clock", "start", "stop"
        ]

        col = 2
        for msg in msg_types:
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(filter_frame, text=msg, variable=var)
            chk.grid(row=0, column=col, padx=4)
            self.filter_vars[msg] = var
            col += 1

        self.block_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            filter_frame,
            text="Block Active Sensing",
            variable=self.block_active
        ).grid(row=1, column=0, columnspan=2, pady=5)

        # ===== COUNTER =====
        counter_frame = ttk.Frame(self.root)
        counter_frame.pack(fill="x", padx=10)

        self.rx_label = ttk.Label(counter_frame, text="RX: 0")
        self.rx_label.pack(side="left", padx=10)

        self.tx_label = ttk.Label(counter_frame, text="TX: 0")
        self.tx_label.pack(side="left", padx=10)

        self.rx_led = tk.Label(counter_frame, width=2, bg="#444444")
        self.rx_led.pack(side="left", padx=5)

        self.tx_led = tk.Label(counter_frame, width=2, bg="#444444")
        self.tx_led.pack(side="left", padx=5)

        # ===== LOG =====
        log_frame = ttk.LabelFrame(self.root, text="MIDI Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log = ScrolledText(log_frame, wrap="none")
        self.log.pack(fill="both", expand=True)

        self.log.configure(
            background="#1e1e1e",
            foreground="#ffffff",
            insertbackground="#ffffff"
        )

        self.setup_log_tags()

        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="x", padx=10, pady=5)

        self.autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bottom_frame,
            text="Auto Scroll",
            variable=self.autoscroll
        ).pack(side="left")

        self.show_timestamp = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bottom_frame,
            text="Show Timestamp",
            variable=self.show_timestamp
        ).pack(side="left", padx=10)

        ttk.Button(
            bottom_frame,
            text="Clear Log",
            command=self.clear_log
        ).pack(side="right")

    # ================= DEVICE =================

    def refresh_devices(self):
        self.in_combo["values"] = mido.get_input_names()
        self.out_combo["values"] = ["None"] + mido.get_output_names()

        if self.in_combo["values"]:
            self.in_combo.current(0)

        self.out_combo.current(0)

    # ================= START / STOP =================

    def start(self):
        if self.running:
            return

        try:
            in_name = self.in_combo.get()
            out_name = self.out_combo.get()

            self.inport = mido.open_input(in_name)
            self.outport = mido.open_output(
                out_name) if out_name != "None" else None

            self.running = True
            threading.Thread(target=self.midi_loop, daemon=True).start()

            self.queue.put(("log", "=== MIDI STARTED ===", "system"))

        except Exception as e:
            self.queue.put(("log", f"ERROR: {e}", "error"))

    def stop(self):
        self.running = False

        if self.inport:
            self.inport.close()
        if self.outport:
            self.outport.close()

        self.queue.put(("log", "=== MIDI STOPPED ===", "system"))

    # ================= MIDI LOOP =================

    def midi_loop(self):
        while self.running:
            try:
                for msg in self.inport.iter_pending():

                    if not self.filter_message(msg):
                        continue

                    self.queue.put(("rx", msg))

                    if self.thru_enabled.get() and self.outport:
                        self.outport.send(msg)
                        self.queue.put(("tx", None))

            except Exception as e:
                self.queue.put(("log", f"MIDI Error: {e}", "error"))
                self.running = False

            time.sleep(0.001)

    # ================= PROCESS QUEUE =================

    def process_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()

                if item[0] == "rx":
                    msg = item[1]
                    self.handle_rx(msg)

                elif item[0] == "tx":
                    self.tx_count += 1
                    self.update_tx()

                elif item[0] == "log":
                    self.write_log(item[1], item[2])

        except Empty:
            pass

        self.root.after(5, self.process_queue)

    # ================= HANDLE RX =================

    def handle_rx(self, msg):
        self.rx_count += 1
        self.update_rx()

        raw_bytes = msg.bytes()

        if (
            msg.type == "sysex"
            and len(raw_bytes) >= 9
            and raw_bytes[1] == 0x43
            and raw_bytes[2] == 0x7E
            and raw_bytes[3] == 0x01
        ):
            b3, b2, b1, b0 = raw_bytes[4:8]
            tempo_value = (b3 << 21) | (b2 << 14) | (b1 << 7) | b0

            if tempo_value != 0:
                bpm = int(60000000 / tempo_value)
                if 5 <= bpm <= 500:
                    self.current_bpm.set(str(bpm))

        hex_bytes = " ".join(f"{b:02X}" for b in raw_bytes)
        desc = msg.type
        formatted = f"{hex_bytes}   {desc}"

        self.write_log(formatted, msg.type)

    # ================= FILTER =================

    def filter_message(self, msg):
        if self.block_active.get() and msg.type == "active_sensing":
            return False

        if msg.type in self.filter_vars:
            if not self.filter_vars[msg.type].get():
                return False

        if self.channel_var.get() != "All":
            if hasattr(msg, "channel"):
                if msg.channel + 1 != int(self.channel_var.get()):
                    return False

        return True

    # ================= LOG =================

    def setup_log_tags(self):
        colors = {
            "note_on": "#00ff88",
            "note_off": "#00aa66",
            "control_change": "#00aaff",
            "program_change": "#bb88ff",
            "pitchwheel": "#ffaa00",
            "sysex": "#ff66ff",
            "clock": "#888888",
            "start": "#55ff55",
            "stop": "#ff4444",
            "system": "#ffffff",
            "error": "#ff0000"
        }

        for tag, color in colors.items():
            self.log.tag_config(tag, foreground=color)

    def write_log(self, text, tag="system"):
        if self.show_timestamp.get():
            timestamp = int(time.time() * 1000) % 100000000
            line = f"[{timestamp}] {text}\n"
        else:
            line = f"{text}\n"

        self.log.insert("end", line, tag)

        if self.autoscroll.get():
            self.log.see("end")

    def clear_log(self):
        self.log.delete("1.0", "end")

    # ================= LED =================

    def update_rx(self):
        self.rx_label.config(text=f"RX: {self.rx_count}")
        self.rx_led.config(bg="#00ff88")
        self.root.after(50, lambda: self.rx_led.config(bg="#444444"))

    def update_tx(self):
        self.tx_label.config(text=f"TX: {self.tx_count}")
        self.tx_led.config(bg="#00aaff")
        self.root.after(50, lambda: self.tx_led.config(bg="#444444"))


if __name__ == "__main__":
    root = tk.Tk()
    app = MidiMonitorGUI(root)
    root.mainloop()
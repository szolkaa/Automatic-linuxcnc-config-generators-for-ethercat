#!/usr/bin/env python3
"""
HAL -> INI intelligent generator (LinuxCNC, EtherCAT, servo)
- GUI (tkinter)
- Load HAL file
- Parse with regex
- Detect joints, cia402 drives, motion links
- Show detected structure with color validation
"""

import os
import re
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from dataclasses import dataclass, field
from typing import Dict, List, Set


# =====================
# Data model
# =====================

@dataclass
class ServoDrive:
    name: str
    joints: Set[int] = field(default_factory=set)
    nets: Set[str] = field(default_factory=set)
    params: Dict[str, str] = field(default_factory=dict)

@dataclass
class Joint:
    index: int
    servos: Set[str] = field(default_factory=set)
    nets: Set[str] = field(default_factory=set)
    motion_mode: str | None = None   # CSP / CSV / UNKNOWN
    axis_type: str | None = None     # LINEAR / ANGULAR

@dataclass
class HalModel:
    joints: Dict[int, Joint] = field(default_factory=dict)
    servos: Dict[str, ServoDrive] = field(default_factory=dict)
    raw_lines: List[str] = field(default_factory=list)


# =====================
# HAL parser (regex based)
# =====================

class HalParser:
    RE_NET = re.compile(r"^net\s+(?P<netname>[\w-]+)\s+(?P<pins>.+)$")
    RE_JOINT_PIN = re.compile(r"joint\.(?P<idx>\d+)\.(?P<name>[\w-]+)")
    RE_CIA_PIN = re.compile(r"cia402\.(?P<idx>\d+)\.(?P<name>[\w-]+)")
    RE_SET_PARAM = re.compile(r"^setp\s+cia402\.(?P<idx>\d+)\.(?P<param>[\w-]+)\s+(?P<val>.+)$")

    def parse(self, text: str) -> HalModel:
        model = HalModel(raw_lines=text.splitlines())

        axis_nets: Dict[str, Set[str]] = {}
        axis_setp: Dict[str, Set[str]] = {}
        axis_netlines: Dict[str, Set[str]] = {}

        for line in model.raw_lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            sm = self.RE_SET_PARAM.match(line)
            if sm:
                idx = int(sm.group('idx'))
                axis = f"cia402.{idx}"

                axis_key = axis
                axis_setp.setdefault(axis_key, set()).add(
                    f"{sm.group('param').lower()}={sm.group('val')}"
                )

                name = axis
                servo = model.servos.setdefault(name, ServoDrive(name=name))
                servo.params[sm.group('param').lower()] = sm.group('val').strip()
                continue

            m = self.RE_NET.match(line)
            if not m:
                continue

            netname = m.group('netname').lower()
            pins_text = m.group('pins')
            pins = re.findall(r"[\w\.-]+", pins_text)

            axis_letter = None
            for pin in pins:
                if self.RE_JOINT_PIN.search(pin) or self.RE_CIA_PIN.search(pin):
                    axis_letter = netname[0] if netname and netname[0] in "xyzabuvw" else None
                    break

            for pin in pins:
                jm = self.RE_JOINT_PIN.search(pin)
                if jm:
                    idx = int(jm.group('idx'))
                    joint = model.joints.setdefault(idx, Joint(index=idx))
                    joint.nets.add(netname)

                    if axis_letter:
                        axis_nets.setdefault(axis_letter, set()).add(netname)

                cm = self.RE_CIA_PIN.search(pin)
                if cm:
                    name = f"cia402.{cm.group('idx')}"
                    servo = model.servos.setdefault(name, ServoDrive(name=name))
                    servo.nets.add(netname)

                    if axis_letter:
                        axis_nets.setdefault(axis_letter, set()).add(netname)

            if axis_letter:
                axis_netlines.setdefault(axis_letter, set()).add(line)

        for j in model.joints.values():
            for s in model.servos.values():
                if j.nets & s.nets:
                    j.servos.add(s.name)
                    s.joints.add(j.index)

        model.axis_nets = axis_nets
        model.axis_setp = axis_setp
        model.axis_netlines = axis_netlines

        return model


# =====================
# Analyzer (CSP/CSV detection)
# =====================

class HalAnalyzer:
    def analyze(self, model: HalModel):
        for j in model.joints.values():
            self._analyze_axis_type(j)
            self._analyze_motion_mode(j, model)

    def _analyze_axis_type(self, joint: Joint):
        if any("deg" in net or "angle" in net for net in joint.nets):
            joint.axis_type = "ANGULAR"
        else:
            joint.axis_type = "LINEAR"

    def _analyze_motion_mode(self, joint: Joint, model: HalModel):
        for servo_name in joint.servos:
            servo = model.servos.get(servo_name)
            if servo:
                if servo.params.get("csp_mode") == "1":
                    joint.motion_mode = "CSP"
                    return
                if servo.params.get("csv_mode") == "1":
                    joint.motion_mode = "CSV"
                    return

        if any("pos_cmd" in net or "motor-pos-cmd" in net for net in joint.nets):
            joint.motion_mode = "CSP"
        elif any("vel_cmd" in net or "velocity_cmd" in net for net in joint.nets):
            joint.motion_mode = "CSV"
        else:
            joint.motion_mode = "UNKNOWN"


# =====================
# Validator (separate section, no impact on INI)
# =====================

@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class HalValidator:
    def validate(self, model: HalModel) -> ValidationResult:
        res = ValidationResult()

        for j in model.joints.values():
            if not j.servos:
                res.errors.append(f"joint.{j.index} has no servo mapping")

        for s in model.servos.values():
            if not s.joints:
                res.errors.append(f"{s.name} has no joint mapping")

        for j in model.joints.values():
            if j.motion_mode == "UNKNOWN":
                res.warnings.append(f"joint.{j.index} motion mode UNKNOWN")

        for s in model.servos.values():
            if len(s.joints) > 1:
                res.errors.append(f"{s.name} mapped to multiple joints: {sorted(s.joints)}")

        for j in model.joints.values():
            if len(j.servos) > 1:
                res.errors.append(f"joint.{j.index} mapped to multiple servos: {sorted(j.servos)}")

        return res


# =====================
# Semantic Validator
# =====================

def norm_line(line: str) -> str:
    return re.sub(r"[0-9xyzabuvwXYZABUVW]", "", line).strip()

EXPECTED_NETS = {
    "CSP": {
        "joint": {"motorposcmd", "motorposfb", "ampenableout"},
        "servo": {"poscmd", "posfb", "enable"},
    },
    "CSV": {
        "joint": {"velcmd", "velfb", "ampenableout"},
        "servo": {"velocitycmd", "velocityfb", "enable"},
    },
    "CST": {
        "joint": {"torquecmd", "torquefb", "ampenableout"},
        "servo": {"torquecmd", "torquefb", "enable"},
    }
}


class SemanticValidator:
    def validate(self, model: HalModel) -> Dict[str, object]:
        result = {
            "essential": True,
            "expected": True,
            "cohesion": True,
            "unmatched": {}
        }

        for j in model.joints.values():
            if not j.servos:
                result["essential"] = False

        for j in model.joints.values():
            if j.motion_mode not in EXPECTED_NETS:
                result["expected"] = False
                continue

            servo_name = next(iter(j.servos), None)
            if not servo_name:
                result["expected"] = False
                continue

            servo = model.servos.get(servo_name)
            if not servo:
                result["expected"] = False
                continue

            joint_nets = {n.lower() for n in j.nets}
            servo_nets = {n.lower() for n in servo.nets}

            exp = EXPECTED_NETS[j.motion_mode]

            for r in exp["joint"]:
                if not any(r in n for n in joint_nets):
                    result["expected"] = False

            for r in exp["servo"]:
                if not any(r in n for n in servo_nets):
                    result["expected"] = False

        axis_netlines = getattr(model, "axis_netlines", {})

        if axis_netlines:
            ref = None
            ref_norm = None

            for axis, lines in axis_netlines.items():
                normalized = {norm_line(l) for l in lines}

                if ref is None:
                    ref = axis
                    ref_norm = normalized
                    continue

                if ref_norm != normalized:
                    result["cohesion"] = False

                    unmatched = set()
                    for l in lines:
                        if norm_line(l) not in ref_norm:
                            unmatched.add(l)

                    result["unmatched"][axis] = unmatched

        return result


# =====================
# GUI
# =====================

AXIS_NAMES = "XYZABCUVW"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HAL → INI Generator (EtherCAT Servo)")
        self.geometry("1000x600")

        self.parser = HalParser()
        self.analyzer = HalAnalyzer()
        self.validator = HalValidator()
        self.semantic_validator = SemanticValidator()
        self.model: HalModel | None = None

        self._build_ui()
        self.after(100, self._set_pane_sizes)

    def _set_pane_sizes(self):
        total_width = self.main.winfo_width()
        if total_width > 0:
            self.main.paneconfigure(self.left_frame, width=int(total_width * 0.7))


    def _build_ui(self):
        bar = tk.Frame(self)
        bar.pack(fill=tk.X)

        left_bar = tk.Frame(bar)
        left_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        right_bar = tk.Frame(bar)
        right_bar.pack(side=tk.RIGHT)

        # Left side: Load and Save
        tk.Button(left_bar, text="📂 Load HAL", command=self.load_hal).pack(side=tk.LEFT, padx=5)
        tk.Button(left_bar, text="💾 Save INI", command=self.save_ini).pack(side=tk.LEFT, padx=5)

        # Gantry at the end of the left section (right edge of left_bar)
        self.gantry_var = tk.BooleanVar(value=False)
        tk.Checkbutton(left_bar, text="Gantry", variable=self.gantry_var).place(relx=0.45, rely=0.0, anchor='n')
        self.gantry_var.trace_add("write", lambda *args: self.apply_gantry_mode())


        self.main = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main)
        self.right_frame = tk.Frame(self.main)
        self.main.add(self.left_frame, stretch='always')
        self.main.add(self.right_frame, stretch='always')

        # LEFT SIDE: grid layout
        self.left_frame.grid_rowconfigure(0, weight=0)
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        # TREEVIEW (fixed height)
        tree_container = tk.Frame(self.left_frame)
        tree_container.grid(row=0, column=0, sticky="nsew")
        tree_container.grid_propagate(False)
        tree_container.config(width=1000, height=250)

        self.tree = ttk.Treeview(tree_container, columns=("value",))
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.heading("#0", text="Element")
        self.tree.heading("value", text="Detected")
        self.tree.tag_configure("ok", foreground="green")
        self.tree.tag_configure("bad", foreground="red")
        self.tree.tag_configure("warn", foreground="orange")

        # BOTTOM: 3 columns with vertical scrollbar
        bottom_canvas = tk.Canvas(self.left_frame)
        bottom_canvas.grid(row=1, column=0, sticky="nsew")

        bottom_scroll = ttk.Scrollbar(self.left_frame, orient="vertical", command=bottom_canvas.yview)
        bottom_scroll.grid(row=1, column=1, sticky="ns")

        bottom_canvas.configure(yscrollcommand=bottom_scroll.set)

        bottom_frame = tk.Frame(bottom_canvas)
        bottom_canvas.create_window((0, 0), window=bottom_frame, anchor="nw")

        bottom_frame.bind("<Configure>", lambda e: bottom_canvas.configure(scrollregion=bottom_canvas.bbox("all")))

        def update_bottom_scroll(*args):
            bottom_canvas.update_idletasks()
            first, last = bottom_canvas.yview()
            if first == 0.0 and last == 1.0:
                bottom_scroll.state(["disabled"])
            else:
                bottom_scroll.state(["!disabled"])

        bottom_canvas.bind("<Configure>", update_bottom_scroll)
        bottom_canvas.bind_all("<MouseWheel>", update_bottom_scroll)

        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=0)
        bottom_frame.grid_columnconfigure(2, weight=1)
        bottom_frame.grid_columnconfigure(3, weight=0)
        bottom_frame.grid_columnconfigure(4, weight=1)

        col1 = tk.Frame(bottom_frame)
        col1.grid(row=0, column=0, sticky="nsew")

        sep1 = tk.Frame(bottom_frame, bg="white", width=2)
        sep1.grid(row=0, column=1, sticky="ns")

        col2 = tk.Frame(bottom_frame)
        col2.grid(row=0, column=2, sticky="nsew")

        sep2 = tk.Frame(bottom_frame, bg="white", width=2)
        sep2.grid(row=0, column=3, sticky="ns")

        col3 = tk.Frame(bottom_frame)
        col3.grid(row=0, column=4, sticky="nsew")

        # Right side: INI output with scrollbar
        text_container = tk.Frame(self.right_frame)
        text_container.pack(fill=tk.BOTH, expand=True)

        self.ini_text = tk.Text(text_container, wrap="none")
        self.ini_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ini_text.configure(state='disabled')

        self.ini_scroll = ttk.Scrollbar(text_container, orient="vertical", command=self.ini_text.yview)
        self.ini_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ini_text.configure(yscrollcommand=self.ini_scroll.set)

        def update_ini_scroll(*args):
            self.ini_text.update_idletasks()
            first, last = self.ini_text.yview()
            if first == 0.0 and last == 1.0:
                self.ini_scroll.state(["disabled"])
            else:
                self.ini_scroll.state(["!disabled"])

        self.ini_text.bind("<Configure>", update_ini_scroll)
        self.ini_text.bind("<MouseWheel>", update_ini_scroll)
        self.ini_text.bind("<KeyRelease>", update_ini_scroll)
        self.ini_text.bind("<<Modified>>", update_ini_scroll)

        # ===== init section widgets =====
        self.sections = {
          "EMC": {"enabled": tk.BooleanVar(value=True), "fields": {
            "MACHINE": tk.StringVar(value="Generated_EtherCAT"),
            "DEBUG": tk.StringVar(value="0"),
            "VERSION": tk.StringVar(value="1.1"),
          }},
          "TRAJ": {"enabled": tk.BooleanVar(value=True), "fields": {
            "COORDINATES": tk.StringVar(value=""),
            "LINEAR_UNITS": tk.StringVar(value="mm"),
            "ANGULAR_UNITS": tk.StringVar(value="degree"),
            "DEFAULT_LINEAR_VELOCITY": tk.StringVar(value="5"),
            "MAX_LINEAR_VELOCITY": tk.StringVar(value="50"),
          }},
          "RS274NGC": {"enabled": tk.BooleanVar(value=True), "fields": {
            "PARAMETER_FILE": tk.StringVar(value="gcodeparam.var"),
          }},

          "EMCMOT": {"enabled": tk.BooleanVar(value=True), "fields": {"EMCMOT": tk.StringVar(value="motmod"), "COMM_TIMEOUT": tk.StringVar(value="1.0"), "SERVO_PERIOD": tk.StringVar(value="1000000"), "HOMEMOD": tk.StringVar(value="cia402_homecomp")}},
          "EMCIO": {"enabled": tk.BooleanVar(value=True), "fields": {"EMCIO": tk.StringVar(value="io"), "CYCLE_TIME": tk.StringVar(value="0.100")}},
          "HAL": {"enabled": tk.BooleanVar(value=False), "fields": {"HALFILE": tk.StringVar(value=""), "HALUI": tk.StringVar(value="halui")}},
          "JOINT": {"enabled": tk.BooleanVar(value=True), "fields": {
            "TYPE": tk.StringVar(value="LINEAR"),
            "HOME": tk.StringVar(value="0"),
            "MIN_LIMIT": tk.StringVar(value="-1000"),
            "MAX_LIMIT": tk.StringVar(value="1000"),
            "MAX_VELOCITY": tk.StringVar(value="50"),
            "MAX_ACCELERATION": tk.StringVar(value="100"),
            "FERROR": tk.StringVar(value="1000"),
            "MIN_FERROR": tk.StringVar(value="1000"),
            "HOME_ABSOLUTE_ENCODER": tk.StringVar(value="2"),
          }},
          "AXIS": {"enabled": tk.BooleanVar(value=True), "fields": {
            "MAX_VELOCITY": tk.StringVar(value="50"),
            "MAX_ACCELERATION": tk.StringVar(value="100"),
            "MIN_LIMIT": tk.StringVar(value="-1000"),
            "MAX_LIMIT": tk.StringVar(value="1000"),
          }},

          "DISPLAY": {"enabled": tk.BooleanVar(value=True), "fields": {
            "DISPLAY": tk.StringVar(value="axis"),
            "EDITOR": tk.StringVar(value="gedit"),
            "POSITION_OFFSET": tk.StringVar(value="RELATIVE"),
            "POSITION_FEEDBACK": tk.StringVar(value="ACTUAL"),
            "ARCDIVISION": tk.StringVar(value="64"),
            "GRIDS": tk.StringVar(value="10mm 20mm 50mm 100mm 1in 2in 5in 10in"),
            "MAX_FEED_OVERRIDE": tk.StringVar(value="1.2"),
            "DEFAULT_LINEAR_VELOCITY": tk.StringVar(value="5"),
            "MAX_ANGULAR_VELOCITY": tk.StringVar(value="50"),
            "MIN_LINEAR_VELOCITY": tk.StringVar(value="0"),
            "MAX_LINEAR_VELOCITY": tk.StringVar(value="50"),
            "CYCLE_TIME": tk.StringVar(value="0.100"),
            "INTRO_GRAPHIC": tk.StringVar(value="linuxcnc.gif"),
            "INTRO_TIME": tk.StringVar(value="1"),
            "INCREMENTS": tk.StringVar(value="5mm 1mm .5mm .1mm .05mm .01mm .005mm"),
          }},
          "KINS": {"enabled": tk.BooleanVar(value=True), "fields": {
            "JOINTS": tk.StringVar(value=""),
            "KINEMATICS": tk.StringVar(value=""),
          }},
          "TASK": {"enabled": tk.BooleanVar(value=True), "fields": {
            "TASK": tk.StringVar(value="milltask"),
            "CYCLE_TIME": tk.StringVar(value="0.010"),
          }},
        }

        self._build_section_ui(col1, "EMC")
        self._build_section_ui(col1, "DISPLAY")
        self._build_section_ui(col1, "KINS")

        self._build_section_ui(col2, "TASK")
        self._build_section_ui(col2, "EMCMOT")
        
        self._build_section_ui(col2, "HAL")
        self._build_section_ui(col2, "TRAJ")
        self._build_section_ui(col2, "EMCIO")

        self._build_section_ui(col3, "RS274NGC")
        self._build_section_ui(col3, "AXIS")
        self._build_section_ui(col3, "JOINT")
        

        for sec in self.sections.values():
            sec["enabled"].trace_add("write", lambda *args: self.update_ini())
            for v in sec["fields"].values():
                v.trace_add("write", lambda *args: self.update_ini())

    def _build_section_ui(self, parent, name):
        sec = self.sections[name]
        frame = tk.LabelFrame(parent, text=name, padx=5, pady=5)
        frame.pack(fill=tk.X, expand=True, padx=5, pady=5)

        cb = tk.Checkbutton(frame, text="Enable", variable=sec["enabled"])
        cb.pack(anchor="w")

        for k, var in sec["fields"].items():
            row = tk.Frame(frame)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=k, width=22, anchor="w").pack(side=tk.LEFT)
            tk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def load_hal(self):
        path = filedialog.askopenfilename(filetypes=[("HAL files", "*.hal"), ("All", "*")])
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()

            self.model = self.parser.parse(text)
            self.analyzer.analyze(self.model)

            coords = self._get_coordinates_string()
            self.sections["TRAJ"]["fields"]["COORDINATES"].set(coords)

            self.sections["KINS"]["fields"]["JOINTS"].set(str(len(self.model.joints)))
            self.sections["KINS"]["fields"]["KINEMATICS"].set(self._get_kinematics_string())

            self.sections["HAL"]["fields"]["HALFILE"].set(os.path.basename(path))
            self.sections["HAL"]["enabled"].set(True)

            self.show_model()
            self.update_ini()
            self.show_validation()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _get_coordinates_string(self):
        if not self.model:
            return ""
        joints = sorted(self.model.joints.keys())
        coords = []
        for idx in joints:
            if idx < len(AXIS_NAMES):
                coords.append(AXIS_NAMES[idx])
            else:
                coords.append(f"J{idx}")
        return " ".join(coords)

    def _get_kinematics_string(self):
        if not self.model:
            return ""
        joints_count = len(self.model.joints)
        letters = "XYZABCDEFGHIJKLMNOPQRST"
        coords = letters[:joints_count]
        return f"trivkins coordinates={coords}"
    def apply_gantry_mode(self):
        if not self.model:
            return

        if self.gantry_var.get():  # Checkbox checked
            # 1) Change in the KINS section
            joints_count = len(self.model.joints)
            coords_letters = "XYZABCDEFGHIJKLMNOPQRST"[:joints_count]

            # Insert kinstype=both and XYYZ for a 4-axis machine
            if joints_count == 4:
                kins_text = f"trivkins kinstype=both coordinates=XYYZ"
            else:
                kins_text = f"trivkins coordinates={coords_letters}"

            self.sections["KINS"]["fields"]["KINEMATICS"].set(kins_text)

            # 2) Change in the TRAJ section
            if joints_count == 4:
                traj_coords = "X Y Y Z"
            else:
                traj_coords = " ".join(coords_letters)

            self.sections["TRAJ"]["fields"]["COORDINATES"].set(traj_coords)

        else:  # Checkbox unchecked → restore default values
            joints_count = len(self.model.joints)
            coords_letters = "XYZABCDEFGHIJKLMNOPQRST"[:joints_count]
            self.sections["KINS"]["fields"]["KINEMATICS"].set(f"trivkins coordinates={coords_letters}")
            self.sections["TRAJ"]["fields"]["COORDINATES"].set(" ".join(coords_letters))

        # Refresh INI display
        self.update_ini()


    def apply_gantry_axis_fix(self):
        """
        Zwraca mapowanie axis -> lista jointów
        Automatycznie obsługuje tryb gantry (XYYZ dla 4 osi, itp.)
        """
        joints = sorted(self.model.joints.keys())
        joints_count = len(joints)

        axis_map = {}

        if not self.gantry_var.get():
            # Standard 1:1 assignment
            for idx in joints:
                axis = AXIS_NAMES[idx] if idx < len(AXIS_NAMES) else f"J{idx}"
                axis_map[axis] = [idx]
            return axis_map

        # ===== GANTRY MODE =====
        # Support for 2, 3, 4, and more joints
        if joints_count == 2:
            axis_map = {
                "X": [0],
                "Y": [1],
            }
        elif joints_count == 3:
            axis_map = {
                "X": [0],
                "Y": [1, 2],
                "Z": [2],
            }
        elif joints_count == 4:
            axis_map = {
                "X": [0],
                "Y": [1, 2],  # master + slave
                "Z": [3],
            }
        else:
            # Fallback: last axis remains individual
            for idx in joints[:-1]:
                axis = AXIS_NAMES[idx] if idx < len(AXIS_NAMES) else f"J{idx}"
                axis_map[axis] = [idx]
            last_idx = joints[-1]
            axis = AXIS_NAMES[last_idx] if last_idx < len(AXIS_NAMES) else f"J{last_idx}"
            axis_map[axis] = [last_idx]

        return axis_map

    def generate_ini_sections(self):
        """
        Generuje sekcje INI dla AXIS i JOINT dynamicznie.
        Uwzględnia tryb Gantry i standardowe przypisanie 1:1.
        """
        out = []

        # Retrieve axis -> joint list mapping
        axis_map = self.apply_gantry_axis_fix()

        # ===== GENERATE AXIS + JOINT SECTION =====
        for axis, joint_list in axis_map.items():
            # AXIS section
            if self.sections["AXIS"]["enabled"].get():
                out.append(f"[AXIS_{axis}]")
                for k, v in self.sections["AXIS"]["fields"].items():
                    value = v.get().strip()
                    if value != "":
                        out.append(f"{k} = {value}")
                out.append("")

            # JOINT sections associated with this AXIS
            if self.sections["JOINT"]["enabled"].get():
                for joint_idx in joint_list:
                    out.append(f"[JOINT_{joint_idx}]")
                    for k, v in self.sections["JOINT"]["fields"].items():
                        value = v.get().strip()
                        if value != "":
                            out.append(f"{k} = {value}")
                    out.append("")

        return "\n".join(out)


    def show_model(self):
        self.tree.delete(*self.tree.get_children())

        if not self.model:
            return

        joints_id = self.tree.insert("", "end", text="JOINTS")
        for j in sorted(self.model.joints.values(), key=lambda x: x.index):
            tag = "ok" if j.servos else "bad"
            servos_str = ", ".join(sorted(j.servos)) if j.servos else "NONE"
            self.tree.insert(
                joints_id,
                "end",
                text=f"joint.{j.index}",
                values=(f"servos={servos_str} type={j.axis_type} mode={j.motion_mode}",),
                tags=(tag,)
            )
        self.tree.item(joints_id, open=False)

        servos_id = self.tree.insert("", "end", text="SERVOS")
        for s in sorted(self.model.servos.values(), key=lambda x: x.name):
            tag = "ok" if s.joints else "bad"
            joints_str = ", ".join(str(i) for i in sorted(s.joints)) if s.joints else "NONE"
            self.tree.insert(
                servos_id,
                "end",
                text=s.name,
                values=(f"joints={joints_str} params={list(s.params.keys())}",),
                tags=(tag,)
            )
        self.tree.item(servos_id, open=False)

    def show_validation(self):
        if not self.model:
            return

        res = self.semantic_validator.validate(self.model)

        validation_id = self.tree.insert("", "end", text="VALIDATION")

        def row(text, ok):
            tag = "ok" if ok else "bad"
            return self.tree.insert(validation_id, "end", text=text, tags=(tag,))

        row("Essential signals", res["essential"])
        cohesion_id = row("Axis cohesion", res["cohesion"])

        if not res["cohesion"]:
            unmatched = res.get("unmatched", {})
            for axis, nets in unmatched.items():
                axis_id = self.tree.insert(cohesion_id, "end", text=f"Axis {axis} unmatched (similar net)")
                for n in nets:
                    self.tree.insert(axis_id, "end", text=n)

        self.tree.item(validation_id, open=True)

    def update_ini(self):
        if not self.model:
            return

        current_view = self.ini_text.yview()

        ini = self.generate_ini()
        self.ini_text.configure(state='normal')
        self.ini_text.delete('1.0', tk.END)
        self.ini_text.insert(tk.END, ini)
        self.ini_text.configure(state='disabled')

        self.ini_text.yview_moveto(current_view[0])

        self.ini_text.update_idletasks()
        first, last = self.ini_text.yview()
        if first == 0.0 and last == 1.0:
            self.ini_scroll.state(["disabled"])
        else:
            self.ini_scroll.state(["!disabled"])

    def save_ini(self):
        if not self.model:
            messagebox.showwarning("Warning", "No HAL loaded yet.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".ini",
            filetypes=[("INI files", "*.ini"), ("All", "*")],
        )
        if not path:
            return

        ini_text = self.generate_ini()

        with open(path, "w", encoding="utf-8") as f:
            f.write(ini_text)

        messagebox.showinfo("Saved", f"INI saved to:\n{path}")

    def generate_ini(self) -> str:
        out = []

        # 1) EMC (column 1)
        if self.sections["EMC"]["enabled"].get():
            out.append("[EMC]")
            for k, v in self.sections["EMC"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")

        # 2) DISPLAY (column 1)
        if self.sections["DISPLAY"]["enabled"].get():
            out.append("[DISPLAY]")
            for k, v in self.sections["DISPLAY"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")

        # 3) KINS (column 1)
        if self.sections["KINS"]["enabled"].get():
            out.append("[KINS]")
            for k, v in self.sections["KINS"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")

        # 4) TASK (column 2)
        if self.sections["TASK"]["enabled"].get():
            out.append("[TASK]")
            for k, v in self.sections["TASK"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")

        # 5) EMCMOT (column 2)
        if self.sections["EMCMOT"]["enabled"].get():
            out.append("[EMCMOT]")
            for k, v in self.sections["EMCMOT"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")

        # 6) TRAJ (column 2)
        if self.sections["TRAJ"]["enabled"].get():
            out.append("[TRAJ]")
            for k, v in self.sections["TRAJ"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")

        # 7) HAL (column 2)
        if self.sections["HAL"]["enabled"].get():
            out.append("[HAL]")
            if self.sections['HAL']['fields']['HALFILE'].get().strip() != "":
                out.append(f"HALFILE = {self.sections['HAL']['fields']['HALFILE'].get()}")
            if self.sections['HAL']['fields']['HALUI'].get().strip() != "":
                out.append(f"HALUI = {self.sections['HAL']['fields']['HALUI'].get()}")
            out.append("")

        # 8) EMCIO (column 2) - NEW
        if self.sections["EMCIO"]["enabled"].get():
            out.append("[EMCIO]")
            for k, v in self.sections["EMCIO"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")
                   
        if self.sections["RS274NGC"]["enabled"].get():
            out.append("[RS274NGC]")
            for k, v in self.sections["RS274NGC"]["fields"].items():
                if v.get().strip() != "":
                    out.append(f"{k} = {v.get()}")
            out.append("")     



        #        9) JOINT + AXIS (column 3) - dynamic with gantry support
        axis_map = self.apply_gantry_axis_fix()

        for axis, joint_list in axis_map.items():
            #        sekcja AXIS
            if self.sections["AXIS"]["enabled"].get():
                out.append(f"[AXIS_{axis}]")
                for k, v in self.sections["AXIS"]["fields"].items():
                    value = v.get().strip()
                    if value != "":
                        out.append(f"{k} = {value}")
                out.append("")

            #        JOINT sections associated with this AXIS
            if self.sections["JOINT"]["enabled"].get():
                for joint_idx in joint_list:
                    out.append(f"[JOINT_{joint_idx}]")
                    for k, v in self.sections["JOINT"]["fields"].items():
                        value = v.get().strip()
                        if value != "":
                            out.append(f"{k} = {value}")
                    out.append("")


        return "\n".join(out)


if __name__ == "__main__":
        app = App()
        app.mainloop()

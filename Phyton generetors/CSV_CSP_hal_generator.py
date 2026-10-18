#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import re


# ======================================================================
# WSPÓLNE FUNKCJE
# ======================================================================
def normalize(name):
    """Normalize pin and halpin names: lowercase, remove underscores and hyphens."""
    name = name.lower().replace("-", "").replace("_", "")
    if name.startswith("drv"):
        name = name[3:]
    return name


def normalize_param(name):
    """Normalize parameter names: lowercase, replace _ with -"""
    return name.lower().replace("_", "-")


# ======================================================================
# PROGRAM CSV  (cia402 + PID w HAL + lcec)
# ======================================================================
class CsvHalGenerator:
    def __init__(self, xml_path, enabled, comp_map, axis_map, pdo_combobox, joint_pins, param_values, pid_param_values):
        self.xml_path = xml_path
        self.enabled = enabled
        self.comp_map = comp_map
        self.axis_map = axis_map
        self.pdo_combobox = pdo_combobox
        self.joint_pins = joint_pins
        self.param_values = param_values
        self.pid_param_values = pid_param_values
        self.slaves = {}
        self.parse_xml()
        self.enabled_joint = {}

        # Normalize joint pins and param values at the start
        for pin, cb in self.joint_pins.items():
            if cb:
                val = cb.get().strip()
                if val and pin != "x-pid.output":
                    cb.set(val.replace("_", "-"))
        for pname, pvar in self.param_values.items():
            val = pvar.get().strip()
            if val:
                pvar.set(val.replace("_", "-"))

    def parse_xml(self):
        """Parses an EtherCAT XML file and saves the PDOs and halPins for each slave."""
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        for slave in root.findall(".//slave"):
            sidx = int(slave.attrib["idx"])
            self.slaves[sidx] = {"rx": [], "tx": []}

            for sm in slave.findall("syncManager"):
                for pdo in sm.findall("pdo"):
                    for entry in pdo.findall("pdoEntry"):
                        obj_str = entry.attrib["idx"]
                        obj = int(obj_str, 16)  # Always treat as hex
                        halpin = entry.attrib.get("halPin", f"obj-{obj:04x}").replace("_", "-")

                        # Direction based on 6040 (rx) and 6041 (tx)
                        if obj == 0x6040:
                            self.slaves[sidx]["rx"].append((obj, halpin))
                        elif obj == 0x6041:
                            self.slaves[sidx]["tx"].append((obj, halpin))
                        else:
                            self.slaves[sidx]["rx"].append((obj, halpin))

    def hal_pin_name(self, cia, obj, halpin, selected):
        """Generuje nazwę CIA402 dla neta, z normalizacją podkreśleń."""
        if selected:
            return f"cia402.{cia}.{selected.replace('_', '-')}"
        return None

    def generate_hal(self):
        """Generuje zawartość pliku HAL dla LinuxCNC + EtherCAT + CIA402."""

        # Joint order and axis-to-joint mapping
        joint_order = []
        for i in sorted(self.axis_map.keys()):
            cfg = self.axis_map[i]
            if cfg["axis"]:
                joint_order.append((cfg["slave"], cfg["axis"], i))

        axis_to_joint = {}
        for idx, (slave, axis, _) in enumerate(sorted(joint_order, key=lambda x: x[0])):
            axis_to_joint[axis] = idx

        # Dynamic count – number of joints in CiA-402
        cia_count = len(axis_to_joint)

        h = []
        h += [
            "# ==========================================",
            "# HAL - CSV mode (cia402 + PID in HAL + lcec)",
            "# ==========================================\n",
            "loadrt [KINS]KINEMATICS",
            "loadrt [EMCMOT]EMCMOT servo_period_nsec=[EMCMOT]SERVO_PERIOD num_joints=[KINS]JOINTS",
            "loadusr -W lcec_conf ethercat-conf.xml",
            f"loadrt cia402 count={cia_count}",  # <- dynamic number of joints
            "loadrt lcec",
        ]

        # Load one PID component for each selected axis.
        if axis_to_joint:
            pid_names = ",".join(f"{axis.lower()}-pid" for axis in axis_to_joint)
            h.append(f"loadrt pid names={pid_names}")
        h.append("")

        # Add servo function
        h.append("addf lcec.read-all servo-thread")
        for axis in axis_to_joint:
            h.append(f"addf cia402.{axis_to_joint[axis]}.read-all servo-thread")
        h.append("addf motion-command-handler servo-thread")
        h.append("addf motion-controller servo-thread")
        for axis in axis_to_joint:
            h.append(f"addf {axis.lower()}-pid.do-pid-calcs servo-thread")

        for axis in axis_to_joint:
            h.append(f"addf cia402.{axis_to_joint[axis]}.write-all servo-thread")
        h.append("addf lcec.write-all servo-thread")
        h.append("")
        h.append("setp iocontrol.0.emc-enable-in 1")
        h.append("")

        # ==========================================
        # AUTOMATIC JOINTS SECTION
        # ==========================================
        required_pins = [
            "joint.0.motor-pos-cmd",
            "joint.0.motor-pos-fb",
            "x-pid.output",
            "joint.0.amp-enable-out",
            "joint.0.amp-fault-in",
            "joint.0.request-custom-homing",
            "joint.0.is-custom-homing",
            "joint.0.custom-homing-finished",
        ]

        # Generate nets for each axis
        for axis in ["X", "Y", "Y2", "Z", "A", "B"]:
            if axis not in axis_to_joint:
                continue

            joint = axis_to_joint[axis]
            cia = joint
            slave = None
            for cfg in self.axis_map.values():
                if cfg["axis"] == axis:
                    slave = cfg["slave"]
                    break

            h.append(f"# -------- AXIS {axis} / joint.{joint} / cia402.{cia} / slave.{slave} --------")

            # CiA-402 parameters – automatic
            for pname, pvar in self.param_values.items():
                val = pvar.get().strip()
                if val:
                    pname_norm = normalize_param(pname)
                    h.append(f"setp cia402.{cia}.{pname_norm} {val}")

            h.append("")

            # PID parameters are configured in the Parameters section.
            pid_name = f"{axis.lower()}-pid"
            for pname, pvar in self.pid_param_values.items():
                val = pvar.get().strip()
                if val:
                    h.append(f"setp {pid_name}.{pname} {val}")
            h.append("")

            # Joint ↔ CiA-402 nets – checkboxes updated dynamically
            for pinname in required_pins:
                if pinname == "joint.0.homed":
                    continue
                cb = self.joint_pins.get(pinname)
                en = self.enabled_joint.get(pinname)
                if not cb or not en or not en.get() or not cb.get().strip():
                    continue
                halpin = cb.get().strip()

                # Joint combobox values may be either a cia402 pin name (legacy)
                # or one/more complete HAL pin names (e.g. x-pid.command).
                pid_name = f"{axis.lower()}-pid"
                selected_pins = halpin.split()
                resolved_pins = []
                for selected_pin in selected_pins:
                    selected_pin = selected_pin.replace("cia402.0.", f"cia402.{cia}.")
                    selected_pin = selected_pin.replace("x-pid.", f"{pid_name}.")
                    selected_pin = selected_pin.replace("_", "-")
                    if "." not in selected_pin:
                        selected_pin = f"cia402.{cia}.{selected_pin}"
                    resolved_pins.append(selected_pin)
                targets = " ".join(resolved_pins)

                if "motor-pos-cmd" in pinname:
                    h.append(f"net {axis}-pos-cmd joint.{joint}.motor-pos-cmd => {targets}")
                elif "motor-pos-fb" in pinname:
                    h.append(f"net {axis}-pos-fb {targets} => joint.{joint}.motor-pos-fb {pid_name}.feedback")
                elif pinname == "x-pid.output":
                    h.append(f"net {axis}-vel-out {pid_name}.output => {targets}")
                elif "amp-enable-out" in pinname:
                    h.append(f"net {axis}-enable joint.{joint}.amp-enable-out => {targets}")
                elif "amp-fault-in" in pinname:
                    h.append(f"net {axis}-amp-fault {targets} => joint.{joint}.amp-fault-in")
                elif "request-custom-homing" in pinname:
                    h.append(f"net {axis}-custom-home joint.{joint}.request-custom-homing => {targets}")
                elif "is-custom-homing" in pinname:
                    h.append(f"net {axis}-is-custom-homing {targets} => joint.{joint}.is-custom-homing")
                elif "custom-homing-finished" in pinname:
                    h.append(f"net {axis}-custom-home-done {targets} => joint.{joint}.custom-homing-finished")

            h.append("")

            # Auto-generate PDO nets (Rx → lcec)
            for obj, halpin in self.slaves.get(slave, {}).get("rx", []):
                if self.enabled.get((slave, obj)):
                    selected = self.pdo_combobox.get((slave, obj))
                    src = self.hal_pin_name(cia, obj, halpin, selected.get() if selected else None)
                    if src:
                        lcec_net = f"lcec.0.{slave}.{halpin}"
                        h.append(f"net {axis}-{halpin} {src} => {lcec_net}")

            # Auto-generate PDO nets (Tx ← lcec)
            for obj, halpin in self.slaves.get(slave, {}).get("tx", []):
                if self.enabled.get((slave, obj)):
                    selected = self.pdo_combobox.get((slave, obj))
                    dst = self.hal_pin_name(cia, obj, halpin, selected.get() if selected else None)
                    if dst:
                        lcec_net = f"lcec.0.{slave}.{halpin}"
                        h.append(f"net {axis}-{halpin} {lcec_net} => {dst}")

            h.append("")

        return "\n".join(h)


class CsvApp(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("LinuxCNC HAL Generator – CSV – FULL PDO Wizard")
        self.geometry("1700x900")

        self.xml_path = None
        self.comp_map = {}
        self.param_values = {}
        # PID parameters are created when cia402.comp is loaded.
        self.pid_param_values = {}

        self.pdo_vars = {}
        self.pdo_combobox = {}
        self.axis_combobox = {}
        self.joint_pins = {}
        self.joint_enable = {}

        self.axis_map = {i: {"axis": None, "slave": None} for i in range(4)}

        top = tk.Frame(self)
        top.pack(fill=tk.X)

        tk.Button(top, text="📂 Load ethercat-conf.xml", command=self.load_xml).pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="📂 Load cia402.comp", command=self.load_comp).pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="💾 Save HAL", command=self.save_hal).pack(side=tk.LEFT, padx=5)

        main = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        self.left = tk.Frame(main, width=650)
        self.left.pack_propagate(False)
        main.add(self.left)

        self.canvas = tk.Canvas(self.left, width=650)
        self.scroll = tk.Scrollbar(self.left, command=self.canvas.yview)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollable = tk.Frame(self.canvas)
        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.hal_text = scrolledtext.ScrolledText(main, font=("Courier", 10))
        main.add(self.hal_text)

        self._update_pending = False

    def _schedule_update(self):
        if self._update_pending:
            return
        self._update_pending = True
        self.after(100, self.update_hal)

    def update_hal(self):
        self._update_pending = False
        self.generate(update_only=True)

    def create_combobox(self, parent, values, row, col, **kwargs):
        cb = ttk.Combobox(parent, values=values, state="readonly", **kwargs)
        cb.grid(row=row, column=col, sticky="w")

        cb._wheel_enabled = False

        def on_mousewheel(event):
            if not cb._wheel_enabled:
                return "break"

        def on_click(event):
            cb._wheel_enabled = True

        def on_close(event=None):
            cb._wheel_enabled = False

        cb.bind("<MouseWheel>", on_mousewheel)
        cb.bind("<Button-4>", on_mousewheel)
        cb.bind("<Button-5>", on_mousewheel)
        cb.bind("<Button-1>", on_click)
        cb.bind("<<ComboboxSelected>>", on_close)
        cb.bind("<FocusOut>", on_close)
        cb.bind("<<ComboboxSelected>>", lambda e: self._schedule_update())

        return cb

    def toggle_combobox(self, pinname):
        cb = self.joint_pins[pinname]
        if self.joint_enable[pinname].get():
            cb.configure(state="readonly")  # Enable combobox
        else:
            cb.configure(state="disabled")  # Disable combobox
        self._schedule_update()   # <- refresh HAL immediately

    def load_comp(self):
        path = filedialog.askopenfilename(filetypes=[("COMP", "*.comp")], parent=self)
        if not path:
            return

        self.comp_map.clear()
        self.param_values.clear()
        self.pid_param_values = {
            "Pgain": tk.StringVar(value="10"),
            "FF1": tk.StringVar(value="1"),
            "Igain": tk.StringVar(value="0"),
            "Dgain": tk.StringVar(value="0"),
            "maxoutput": tk.StringVar(value="4000"),
        }

        with open(path) as f:
            content = f.read()

        pins = re.findall(r'pin\s+(in|out|io)\s+(unsigned|signed|float|bit)\s+(\w+)', content)
        for _, _, name in pins:
            self.comp_map[name] = name

        params = re.findall(r'param\s+(rw|ro)\s+(unsigned|signed|float|bit)\s+(\w+)', content)
        for _, _, name in params:
            normalized_name = normalize(name)
            if normalized_name in ("posscale", "positionscale", "velscale", "veloscale", "velocityscale"):
                default_value = "1677721.6"
            elif normalized_name == "cspmode":
                default_value = "0"
            else:
                default_value = ""
            self.param_values[name] = tk.StringVar(value=default_value)

        messagebox.showinfo("OK", f"Loaded cia402.comp – {len(self.comp_map)} pins, {len(self.param_values)} parameters", parent=self)
        if self.xml_path:
            self.refresh_wizard()

    def load_xml(self):
        self.xml_path = filedialog.askopenfilename(filetypes=[("XML", "*.xml")], parent=self)
        if self.xml_path:
            self.refresh_wizard()

    def refresh_wizard(self):
        for w in self.scrollable.winfo_children():
            w.destroy()

        self.pdo_vars.clear()
        self.pdo_combobox.clear()
        self.axis_combobox.clear()
        self.joint_pins.clear()
        self.joint_enable.clear()

        axis_options = ["", "X", "Y", "Y2", "Z", "A", "B"]
        bold_font = ("Arial", 10, "bold")

        tk.Label(self.scrollable, text="PDO / Pins", font=bold_font).grid(row=0, column=0, sticky="w")
        tk.Label(self.scrollable, text="Ciacomp Pins", font=bold_font).grid(row=0, column=1, sticky="w", padx=(0, 12))

        sep = ttk.Separator(self.scrollable, orient="vertical")
        sep.grid(row=0, column=2, rowspan=999, sticky="ns", padx=5)

        tk.Label(self.scrollable, text="General", font=bold_font).grid(row=0, column=3, sticky="w")

        general_row = 1
        if self.param_values or self.pid_param_values:
            tk.Label(self.scrollable, text="Parameters", font=bold_font).grid(row=general_row, column=3, sticky="w")
            general_row += 1

            for pname, pvar in self.param_values.items():
                tk.Label(self.scrollable, text=pname).grid(row=general_row, column=3, sticky="w")
                entry = tk.Entry(self.scrollable, textvariable=pvar)
                entry.grid(row=general_row, column=4, sticky="w")
                entry.bind("<KeyRelease>", lambda e: self._schedule_update())

                general_row += 1

            # PID parameters use the same editable setp-style controls.
            for pname, pvar in self.pid_param_values.items():
                tk.Label(self.scrollable, text=f"PID {pname}").grid(row=general_row, column=3, sticky="w")
                entry = tk.Entry(self.scrollable, textvariable=pvar)
                entry.grid(row=general_row, column=4, sticky="w")
                entry.bind("<KeyRelease>", lambda e: self._schedule_update())
                general_row += 1

        if self.comp_map:
            tk.Label(self.scrollable, text="Joints", font=bold_font).grid(row=general_row, column=3, sticky="w")
            general_row += 1

            joint_order = [
                "joint.0.motor-pos-cmd",
                "joint.0.motor-pos-fb",
                "x-pid.output",
                "joint.0.amp-enable-out",
                "joint.0.amp-fault-in",
                "",
                "",
                "joint.0.request-custom-homing",
                "joint.0.is-custom-homing",
                "joint.0.custom-homing-finished",
            ]

            joint_suggestions = {
                "joint.0.amp-enable-out": "cia402.0.enable x-pid.enable",
                "joint.0.motor-pos-cmd": "x-pid.command",
                "joint.0.motor-pos-fb": "pos-fb",
                "x-pid.output": "velocity_cmd",
                "joint.0.amp-fault-in": "drv_fault",
                "joint.0.request-custom-homing": "home",
                "joint.0.is-custom-homing": "stat_homing",
                "joint.0.custom-homing-finished": "stat_homed",
            }

            pin_list = list(self.comp_map.keys())
            # Extra HAL choices for PID and combined enable wiring.
            joint_extra_choices = ["x-pid.command", "x-pid.output", "velocity_cmd", "cia402.0.enable x-pid.enable"]
            joint_pin_choices = list(dict.fromkeys(pin_list + joint_extra_choices))

            for pinname in joint_order:
                if pinname == "":
                    tk.Label(self.scrollable, text="").grid(row=general_row, column=3)
                    general_row += 1
                    continue

                if pinname == "joint.0.request-custom-homing":
                    tk.Label(self.scrollable, text="Homing", font=("Arial", 10, "bold")).grid(
                        row=general_row, column=3, sticky="w"
                    )
                    general_row += 1

                var = tk.BooleanVar(value=True)

                self.joint_enable[pinname] = var

                # Checkbox with callback to enable/disable combobox
                chk = tk.Checkbutton(
                    self.scrollable,
                    text=("joint.0.motor-pos-fb x-pid.feedback" if pinname == "joint.0.motor-pos-fb" else pinname),
                    variable=var,
                    command=lambda p=pinname: self.toggle_combobox(p)
                )
                chk.grid(row=general_row, column=3, sticky="w")

                cb = self.create_combobox(self.scrollable, joint_pin_choices, general_row, 4)
                sugg = joint_suggestions.get(pinname)
                if sugg:
                    if sugg in joint_pin_choices:
                        cb.set(sugg)
                    else:
                        for pin in joint_pin_choices:
                            if normalize(pin) == normalize(sugg):
                                cb.set(pin)
                                break

                self.joint_pins[pinname] = cb
                general_row += 1

                tk.Label(self.scrollable, text="").grid(row=general_row, column=3)
                general_row += 1

        # Load slave and PDO
        row = 1
        tree = ET.parse(self.xml_path)
        root = tree.getroot()

        for slave in root.findall(".//slave"):
            sidx = int(slave.attrib["idx"])
            tk.Label(self.scrollable, text=f"Slave {sidx}", font=bold_font).grid(row=row, column=0, sticky="w")

            has_pdo = any(sm.findall("pdo") for sm in slave.findall("syncManager"))
            if has_pdo:
                cb = self.create_combobox(self.scrollable, axis_options, row, 1, font=bold_font)
                self.axis_combobox[sidx] = cb

            row += 1
            if not has_pdo:
                row += 1
                continue

            for sm in slave.findall("syncManager"):
                for pdo in sm.findall("pdo"):
                    for entry in pdo.findall("pdoEntry"):
                        obj = int(entry.attrib["idx"], 16)
                        halpin = entry.attrib.get("halPin", f"obj-{obj:04x}")

                        var = tk.BooleanVar(value=True)
                        self.pdo_vars[(sidx, obj)] = var

                        cb2 = self.create_combobox(self.scrollable, list(self.comp_map.keys()), row, 1)
                        for pin in self.comp_map:
                            if normalize(pin) == normalize(halpin):
                                cb2.set(pin)
                                break

                        self.pdo_combobox[(sidx, obj)] = cb2
                        tk.Checkbutton(
                            self.scrollable,
                            text=f"0x{obj:04X} {halpin}",
                            variable=var,
                            command=self._schedule_update,
                        ).grid(row=row, column=0, sticky="w")
                        row += 1

            row += 1

        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._schedule_update()

    def generate(self, update_only=False):
        self.axis_map = {i: {"axis": None, "slave": None} for i in range(4)}

        axis_used = {}
        for slave, cb in self.axis_combobox.items():
            if cb.get():
                axis_used[cb.get()] = slave

        i = 0
        for axis in ["X", "Y", "Y2", "Z", "A", "B"]:
            if axis in axis_used:
                self.axis_map[i]["axis"] = axis
                self.axis_map[i]["slave"] = axis_used[axis]
                i += 1

        enabled = {k: v.get() for k, v in self.pdo_vars.items()}

        gen = CsvHalGenerator(
            self.xml_path,
            enabled,
            self.comp_map,
            self.axis_map,
            self.pdo_combobox,
            self.joint_pins,
            self.param_values,
            self.pid_param_values,
        )
        gen.enabled_joint = self.joint_enable

        hal = gen.generate_hal()
        self.hal_text.delete("1.0", tk.END)
        self.hal_text.insert(tk.END, hal)

        if not update_only:
            self._schedule_update()

    def save_hal(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".hal",
            filetypes=[("HAL files", "*.hal"), ("All files", "*.*")],
            title="Zapisz plik HAL",
            parent=self,
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.hal_text.get("1.0", tk.END))
            messagebox.showinfo("Saved", path, parent=self)


# ======================================================================
# PROGRAM CSP  (cia402 + lcec)
# ======================================================================
class CspHalGenerator:
    def __init__(self, xml_path, enabled, comp_map, axis_map, pdo_combobox, joint_pins, param_values):
        self.xml_path = xml_path
        self.enabled = enabled
        self.comp_map = comp_map
        self.axis_map = axis_map
        self.pdo_combobox = pdo_combobox
        self.joint_pins = joint_pins
        self.param_values = param_values
        self.slaves = {}
        self.parse_xml()
        self.enabled_joint = {}

        # Normalize joint pins and param values at the start
        for pin, cb in self.joint_pins.items():
            if cb:
                val = cb.get().strip()
                if val:
                    cb.set(val.replace("_", "-"))
        for pname, pvar in self.param_values.items():
            val = pvar.get().strip()
            if val:
                pvar.set(val.replace("_", "-"))

    def parse_xml(self):
        """Parses an EtherCAT XML file and saves the PDOs and halPins for each slave."""
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        for slave in root.findall(".//slave"):
            sidx = int(slave.attrib["idx"])
            self.slaves[sidx] = {"rx": [], "tx": []}

            for sm in slave.findall("syncManager"):
                for pdo in sm.findall("pdo"):
                    for entry in pdo.findall("pdoEntry"):
                        obj_str = entry.attrib["idx"]
                        obj = int(obj_str, 16)  # Always treat as hex
                        halpin = entry.attrib.get("halPin", f"obj-{obj:04x}").replace("_", "-")

                        # Direction based on 6040 (rx) and 6041 (tx)
                        if obj == 0x6040:
                            self.slaves[sidx]["rx"].append((obj, halpin))
                        elif obj == 0x6041:
                            self.slaves[sidx]["tx"].append((obj, halpin))
                        else:
                            self.slaves[sidx]["rx"].append((obj, halpin))

    def hal_pin_name(self, cia, obj, halpin, selected):
        """Generuje nazwę CIA402 dla neta, z normalizacją podkreśleń."""
        if selected:
            return f"cia402.{cia}.{selected.replace('_', '-')}"
        return None

    def generate_hal(self):
        """Generuje zawartość pliku HAL dla LinuxCNC + EtherCAT + CIA402."""

        # Joint order and axis-to-joint mapping
        joint_order = []
        for i in sorted(self.axis_map.keys()):
            cfg = self.axis_map[i]
            if cfg["axis"]:
                joint_order.append((cfg["slave"], cfg["axis"], i))

        axis_to_joint = {}
        for idx, (slave, axis, _) in enumerate(sorted(joint_order, key=lambda x: x[0])):
            axis_to_joint[axis] = idx

        # Dynamic count – number of joints in CiA-402
        cia_count = len(axis_to_joint)

        h = []
        h += [
            "# ==========================================",
            "# HAL - CSP mode (cia402 + lcec)",
            "# ==========================================\n",
            "loadrt [KINS]KINEMATICS",
            "loadrt [EMCMOT]EMCMOT servo_period_nsec=[EMCMOT]SERVO_PERIOD num_joints=[KINS]JOINTS",
            "loadusr -W lcec_conf ethercat-conf.xml",
            f"loadrt cia402 count={cia_count}",  # <- dynamic number of joints
            "loadrt lcec",
            "",
        ]

        # Add servo function
        h.append("addf lcec.read-all servo-thread")
        for axis in axis_to_joint:
            h.append(f"addf cia402.{axis_to_joint[axis]}.read-all servo-thread")
        h.append("addf motion-command-handler servo-thread")
        h.append("addf motion-controller servo-thread")

        for axis in axis_to_joint:
            h.append(f"addf cia402.{axis_to_joint[axis]}.write-all servo-thread")
        h.append("addf lcec.write-all servo-thread")
        h.append("")
        h.append("setp iocontrol.0.emc-enable-in 1")
        h.append("")

        # ==========================================
        # AUTOMATIC JOINTS SECTION
        # ==========================================
        required_pins = [
            "joint.0.motor-pos-cmd",
            "joint.0.motor-pos-fb",
            "joint.0.amp-enable-out",
            "joint.0.amp-fault-in",
            "joint.0.request-custom-homing",
            "joint.0.is-custom-homing",
            "joint.0.custom-homing-finished",
        ]

        # Generate nets for each axis
        for axis in ["X", "Y", "Y2", "Z", "A", "B"]:
            if axis not in axis_to_joint:
                continue

            joint = axis_to_joint[axis]
            cia = joint
            slave = None
            for cfg in self.axis_map.values():
                if cfg["axis"] == axis:
                    slave = cfg["slave"]
                    break

            h.append(f"# -------- AXIS {axis} / joint.{joint} / cia402.{cia} / slave.{slave} --------")

            # CiA-402 parameters – automatic
            for pname, pvar in self.param_values.items():
                val = pvar.get().strip()
                if val:
                    pname_norm = normalize_param(pname)
                    h.append(f"setp cia402.{cia}.{pname_norm} {val}")

            h.append("")

            # Joint ↔ CiA-402 nets – checkboxes updated dynamically
            for pinname in required_pins:
                if pinname == "joint.0.homed":
                    continue
                cb = self.joint_pins.get(pinname)
                en = self.enabled_joint.get(pinname)
                if not cb or not en or not en.get() or not cb.get().strip():
                    continue
                halpin = cb.get().strip()

                if "motor-pos-cmd" in pinname:
                    h.append(f"net {axis}-pos-cmd joint.{joint}.motor-pos-cmd => cia402.{cia}.{halpin}")
                elif "motor-pos-fb" in pinname:
                    h.append(f"net {axis}-pos-fb cia402.{cia}.{halpin} => joint.{joint}.motor-pos-fb")
                elif "amp-enable-out" in pinname:
                    h.append(f"net {axis}-enable joint.{joint}.amp-enable-out => cia402.{cia}.{halpin}")
                elif "amp-fault-in" in pinname:
                    h.append(f"net {axis}-amp-fault cia402.{cia}.{halpin} => joint.{joint}.amp-fault-in")
                elif "request-custom-homing" in pinname:
                    h.append(f"net {axis}-custom-home joint.{joint}.request-custom-homing => cia402.{cia}.{halpin}")
                elif "is-custom-homing" in pinname:
                    h.append(f"net {axis}-is-custom-homing cia402.{cia}.{halpin} => joint.{joint}.is-custom-homing")
                elif "custom-homing-finished" in pinname:
                    h.append(f"net {axis}-custom-home-done cia402.{cia}.{halpin} => joint.{joint}.custom-homing-finished")

            h.append("")

            # Auto-generate PDO nets (Rx → lcec)
            for obj, halpin in self.slaves.get(slave, {}).get("rx", []):
                if self.enabled.get((slave, obj)):
                    selected = self.pdo_combobox.get((slave, obj))
                    src = self.hal_pin_name(cia, obj, halpin, selected.get() if selected else None)
                    if src:
                        lcec_net = f"lcec.0.{slave}.{halpin}"
                        h.append(f"net {axis}-{halpin} {src} => {lcec_net}")

            # Auto-generate PDO nets (Tx ← lcec)
            for obj, halpin in self.slaves.get(slave, {}).get("tx", []):
                if self.enabled.get((slave, obj)):
                    selected = self.pdo_combobox.get((slave, obj))
                    dst = self.hal_pin_name(cia, obj, halpin, selected.get() if selected else None)
                    if dst:
                        lcec_net = f"lcec.0.{slave}.{halpin}"
                        h.append(f"net {axis}-{halpin} {lcec_net} => {dst}")

            h.append("")

        return "\n".join(h)


class CspApp(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("LinuxCNC HAL Generator – CSP – FULL PDO Wizard")
        self.geometry("1700x900")

        self.xml_path = None
        self.comp_map = {}
        self.param_values = {}

        self.pdo_vars = {}
        self.pdo_combobox = {}
        self.axis_combobox = {}
        self.joint_pins = {}
        self.joint_enable = {}

        self.axis_map = {i: {"axis": None, "slave": None} for i in range(4)}

        top = tk.Frame(self)
        top.pack(fill=tk.X)

        tk.Button(top, text="📂 Load ethercat-conf.xml", command=self.load_xml).pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="📂 Load cia402.comp", command=self.load_comp).pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="💾 Save HAL", command=self.save_hal).pack(side=tk.LEFT, padx=5)

        main = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        self.left = tk.Frame(main, width=650)
        self.left.pack_propagate(False)
        main.add(self.left)

        self.canvas = tk.Canvas(self.left, width=650)
        self.scroll = tk.Scrollbar(self.left, command=self.canvas.yview)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollable = tk.Frame(self.canvas)
        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.hal_text = scrolledtext.ScrolledText(main, font=("Courier", 10))
        main.add(self.hal_text)

        self._update_pending = False

    def _schedule_update(self):
        if self._update_pending:
            return
        self._update_pending = True
        self.after(100, self.update_hal)

    def update_hal(self):
        self._update_pending = False
        self.generate(update_only=True)

    def create_combobox(self, parent, values, row, col, **kwargs):
        cb = ttk.Combobox(parent, values=values, state="readonly", **kwargs)
        cb.grid(row=row, column=col, sticky="w")

        cb._wheel_enabled = False

        def on_mousewheel(event):
            if not cb._wheel_enabled:
                return "break"

        def on_click(event):
            cb._wheel_enabled = True

        def on_close(event=None):
            cb._wheel_enabled = False

        cb.bind("<MouseWheel>", on_mousewheel)
        cb.bind("<Button-4>", on_mousewheel)
        cb.bind("<Button-5>", on_mousewheel)
        cb.bind("<Button-1>", on_click)
        cb.bind("<<ComboboxSelected>>", on_close)
        cb.bind("<FocusOut>", on_close)
        cb.bind("<<ComboboxSelected>>", lambda e: self._schedule_update())

        return cb

    def toggle_combobox(self, pinname):
        cb = self.joint_pins[pinname]
        if self.joint_enable[pinname].get():
            cb.configure(state="readonly")  # Enable combobox
        else:
            cb.configure(state="disabled")  # Disable combobox
        self._schedule_update()   # <- refresh HAL immediately

    def load_comp(self):
        path = filedialog.askopenfilename(filetypes=[("COMP", "*.comp")], parent=self)
        if not path:
            return

        self.comp_map.clear()
        self.param_values.clear()

        with open(path) as f:
            content = f.read()

        pins = re.findall(r'pin\s+(in|out|io)\s+(unsigned|signed|float|bit)\s+(\w+)', content)
        for _, _, name in pins:
            self.comp_map[name] = name

        params = re.findall(r'param\s+(rw|ro)\s+(unsigned|signed|float|bit)\s+(\w+)', content)
        for _, _, name in params:
            self.param_values[name] = tk.StringVar(value="")

        messagebox.showinfo("OK", f"Loaded cia402.comp – {len(self.comp_map)} pins, {len(self.param_values)} parameters", parent=self)
        if self.xml_path:
            self.refresh_wizard()

    def load_xml(self):
        self.xml_path = filedialog.askopenfilename(filetypes=[("XML", "*.xml")], parent=self)
        if self.xml_path:
            self.refresh_wizard()

    def refresh_wizard(self):
        for w in self.scrollable.winfo_children():
            w.destroy()

        self.pdo_vars.clear()
        self.pdo_combobox.clear()
        self.axis_combobox.clear()
        self.joint_pins.clear()
        self.joint_enable.clear()

        axis_options = ["", "X", "Y", "Y2", "Z", "A", "B"]
        bold_font = ("Arial", 10, "bold")

        tk.Label(self.scrollable, text="PDO / Pins", font=bold_font).grid(row=0, column=0, sticky="w")
        tk.Label(self.scrollable, text="Ciacomp Pins", font=bold_font).grid(row=0, column=1, sticky="w", padx=(0, 12))

        sep = ttk.Separator(self.scrollable, orient="vertical")
        sep.grid(row=0, column=2, rowspan=999, sticky="ns", padx=5)

        tk.Label(self.scrollable, text="General", font=bold_font).grid(row=0, column=3, sticky="w")

        general_row = 1
        if self.param_values:
            tk.Label(self.scrollable, text="Parameters", font=bold_font).grid(row=general_row, column=3, sticky="w")
            general_row += 1

            for pname, pvar in self.param_values.items():
                tk.Label(self.scrollable, text=pname).grid(row=general_row, column=3, sticky="w")
                entry = tk.Entry(self.scrollable, textvariable=pvar)
                entry.grid(row=general_row, column=4, sticky="w")
                entry.bind("<KeyRelease>", lambda e: self._schedule_update())

                if normalize(pname) == "posscale":
                    pvar.set("1677721.6")
                elif normalize(pname) == "cspmode":
                    pvar.set("1")

                general_row += 1

        if self.comp_map:
            tk.Label(self.scrollable, text="Joints", font=bold_font).grid(row=general_row, column=3, sticky="w")
            general_row += 1

            joint_order = [
                "joint.0.motor-pos-cmd",
                "joint.0.motor-pos-fb",
                "joint.0.amp-enable-out",
                "joint.0.amp-fault-in",
                "",
                "",
                "joint.0.request-custom-homing",
                "joint.0.is-custom-homing",
                "joint.0.custom-homing-finished",
            ]

            joint_suggestions = {
                "joint.0.amp-enable-out": "enable",
                "joint.0.motor-pos-cmd": "pos_cmd",
                "joint.0.motor-pos-fb": "pos_fb",
                "joint.0.amp-fault-in": "drv_fault",
                "joint.0.request-custom-homing": "home",
                "joint.0.is-custom-homing": "stat_homing",
                "joint.0.custom-homing-finished": "stat_homed",
            }

            pin_list = list(self.comp_map.keys())

            for pinname in joint_order:
                if pinname == "":
                    tk.Label(self.scrollable, text="").grid(row=general_row, column=3)
                    general_row += 1
                    continue

                if pinname == "joint.0.request-custom-homing":
                    tk.Label(self.scrollable, text="Homing", font=("Arial", 10, "bold")).grid(
                        row=general_row, column=3, sticky="w"
                    )
                    general_row += 1

                var = tk.BooleanVar(value=True)

                self.joint_enable[pinname] = var

                # Checkbox with callback to enable/disable combobox
                chk = tk.Checkbutton(
                    self.scrollable,
                    text=pinname,
                    variable=var,
                    command=lambda p=pinname: self.toggle_combobox(p)
                )
                chk.grid(row=general_row, column=3, sticky="w")

                cb = self.create_combobox(self.scrollable, pin_list, general_row, 4)
                sugg = joint_suggestions.get(pinname)
                if sugg:
                    for pin in pin_list:
                        if normalize(pin) == normalize(sugg):
                            cb.set(pin)
                            break

                self.joint_pins[pinname] = cb
                general_row += 1

                tk.Label(self.scrollable, text="").grid(row=general_row, column=3)
                general_row += 1

        # Load slave and PDO
        row = 1
        tree = ET.parse(self.xml_path)
        root = tree.getroot()

        for slave in root.findall(".//slave"):
            sidx = int(slave.attrib["idx"])
            tk.Label(self.scrollable, text=f"Slave {sidx}", font=bold_font).grid(row=row, column=0, sticky="w")

            has_pdo = any(sm.findall("pdo") for sm in slave.findall("syncManager"))
            if has_pdo:
                cb = self.create_combobox(self.scrollable, axis_options, row, 1, font=bold_font)
                self.axis_combobox[sidx] = cb

            row += 1
            if not has_pdo:
                row += 1
                continue

            for sm in slave.findall("syncManager"):
                for pdo in sm.findall("pdo"):
                    for entry in pdo.findall("pdoEntry"):
                        obj = int(entry.attrib["idx"], 16)
                        halpin = entry.attrib.get("halPin", f"obj-{obj:04x}")

                        var = tk.BooleanVar(value=True)
                        self.pdo_vars[(sidx, obj)] = var

                        cb2 = self.create_combobox(self.scrollable, list(self.comp_map.keys()), row, 1)
                        for pin in self.comp_map:
                            if normalize(pin) == normalize(halpin):
                                cb2.set(pin)
                                break

                        self.pdo_combobox[(sidx, obj)] = cb2
                        tk.Checkbutton(
                            self.scrollable,
                            text=f"0x{obj:04X} {halpin}",
                            variable=var,
                            command=self._schedule_update,
                        ).grid(row=row, column=0, sticky="w")
                        row += 1

            row += 1

        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._schedule_update()

    def generate(self, update_only=False):
        self.axis_map = {i: {"axis": None, "slave": None} for i in range(4)}

        axis_used = {}
        for slave, cb in self.axis_combobox.items():
            if cb.get():
                axis_used[cb.get()] = slave

        i = 0
        for axis in ["X", "Y", "Y2", "Z", "A", "B"]:
            if axis in axis_used:
                self.axis_map[i]["axis"] = axis
                self.axis_map[i]["slave"] = axis_used[axis]
                i += 1

        enabled = {k: v.get() for k, v in self.pdo_vars.items()}

        gen = CspHalGenerator(
            self.xml_path,
            enabled,
            self.comp_map,
            self.axis_map,
            self.pdo_combobox,
            self.joint_pins,
            self.param_values,
        )
        gen.enabled_joint = self.joint_enable

        hal = gen.generate_hal()
        self.hal_text.delete("1.0", tk.END)
        self.hal_text.insert(tk.END, hal)

        if not update_only:
            self._schedule_update()

    def save_hal(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".hal",
            filetypes=[("HAL files", "*.hal"), ("All files", "*.*")],
            title="Zapisz plik HAL",
            parent=self,
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.hal_text.get("1.0", tk.END))
            messagebox.showinfo("Saved", path, parent=self)


# ======================================================================
# OKNO STARTOWE – wybór programu CSV / CSP
# ======================================================================
class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinuxCNC HAL Generator")
        self.geometry("400x200")

        self.windows = {"CSV": None, "CSP": None}
        self.classes = {"CSV": CsvApp, "CSP": CspApp}

        big_font = ("Arial", 36, "bold")

        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        for col, name in enumerate(("CSV", "CSP")):
            lbl = tk.Label(
                container,
                text=name,
                font=big_font,
                cursor="hand2",
                relief=tk.RAISED,
                bd=6,
            )
            lbl.grid(row=0, column=col, sticky="nsew", padx=15, pady=15)
            lbl.bind("<Button-1>", lambda e, n=name: self.open_program(n))

    def open_program(self, name):
        win = self.classes[name](self)
        self.windows[name] = win
        # Po wyborze okno startowe znika; zamknięcie programu kończy całość
        win.protocol("WM_DELETE_WINDOW", self.destroy)
        self.withdraw()


if __name__ == "__main__":
    Launcher().mainloop()

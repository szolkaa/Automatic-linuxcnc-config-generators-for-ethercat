import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

# =========================
# Auxiliary
# =========================
def parse_int(val):
    if not val:
        return 0
    v = val.strip().lower().replace("#", "")
    if v.startswith("0x"):
        return int(v, 16)
    if v.startswith("x"):
        return int("0x" + v[1:], 16)
    return int(v)

def hex8(v):
    return f"{v:08X}"

def dec(v):
    return str(v)

# =========================
# HAL MAPPINGS (CiA-402)
# =========================
CIA402_HAL = {
    "6040": "control-word",
    "6041": "status-word",
    "6060": "modes-of-operation",
    "6061": "modes-of-operation-display",
    "607A": "target-position",
    "6064": "actual-position",
    "60FF": "target-velocity",
    "606C": "actual-velocity",
    "6071": "target-torque",
    "6077": "actual-torque",
}

CUSTOM_HAL_PINS = {
    "60B8": "probe-cmd",
    "6060": "opmode",
    "603F": "error-code",
    "60B9": "probe-status",
    "60BA": "probe1-rising",
    "60FD": "mydigitalin",
    "6061": "opmode-display",
}

# =========================
# Main Class
# =========================
class ESI2LinuxCNC:
    def __init__(self, root):
        self.root = root
        self.root.title("ESI → LinuxCNC")
        self.esi = None

        # ===== GRID KONFIG =====
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=9)
        root.rowconfigure(0, weight=1)

        # =========================
        # Left Panel – Buttons
        # =========================
        self.left = tk.Frame(root)
        self.left.grid(row=0, column=0, sticky="nswe")
        self.left.columnconfigure(0, weight=1)

        btn_opts = {"fill": "x", "padx": 6, "pady": 6, "ipady": 18}

        # Load ESI + Automatic Conversion
        tk.Button(self.left, text="Load ESI", command=self.load_esi)\
            .pack(**btn_opts)

        # Replace names (halPin only)
        tk.Button(self.left, text="Rename HAL pins (PDO)", command=self.replace_names)\
            .pack(**btn_opts)

        # NEW BUTTON: reduce PDO to CSP essentials
        tk.Button(self.left, text="Reduce pdo to csp essential", command=self.reduce_pdo_csp)\
            .pack(**btn_opts)

        tk.Button(self.left, text="Duplicate slave", command=self.duplicate_slave)\
            .pack(**btn_opts)
        tk.Button(self.left, text="Save XML", command=self.save_xml)\
            .pack(**btn_opts)

        # =========================
        # RIGHT COLUMN – XML
        # =========================
        self.right = tk.Frame(root)
        self.right.grid(row=0, column=1, sticky="nswe")
        self.right.rowconfigure(0, weight=1)
        self.right.columnconfigure(0, weight=1)

        self.text = tk.Text(self.right, wrap="none")
        self.text.grid(row=0, column=0, sticky="nswe")

        yscroll = tk.Scrollbar(self.right, orient="vertical", command=self.text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")

        xscroll = tk.Scrollbar(self.right, orient="horizontal", command=self.text.xview)
        xscroll.grid(row=1, column=0, sticky="ew")

        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

    # =========================
    # LOAD ESI (with automatic conversion)
    # =========================
    def load_esi(self):
        path = filedialog.askopenfilename(filetypes=[("ESI XML", "*.xml"), ("All files", "*.*")])
        if not path:
            return

        root = ET.parse(path).getroot()
        vendor = parse_int(root.findtext(".//Vendor/Id"))
        t = root.find(".//Device/Type")
        product = parse_int(t.attrib.get("ProductCode"))
        revision = parse_int(t.attrib.get("RevisionNo"))
        name = t.text.strip() if t.text else "EtherCAT-Slave"

        def pdos(tag):
            out = []
            for p in root.findall(f".//{tag}"):
                idx = p.findtext("Index", "0").replace("#x", "").replace("0x", "").upper()
                entries = []
                for e in p.findall("Entry"):
                    entries.append({
                        "idx": e.findtext("Index", "0").replace("#x", "").replace("0x", "").upper(),
                        "sub": e.findtext("SubIndex", "0"),
                        "bits": e.findtext("BitLen", "0"),
                        "dtype": e.findtext("DataType", "").upper()
                    })
                out.append({"index": idx, "entries": entries})
            return out

        self.esi = {
            "vendor": vendor,
            "product": product,
            "revision": revision,
            "name": name,
            "rx": pdos("RxPdo"),
            "tx": pdos("TxPdo")
        }

        # Automatic conversion after loading
        self.convert()
        messagebox.showinfo("OK", "ESI loaded and converted")

    # =========================
    # HAL for pdoEntry – only 6040, 6041 = u32, others = s32
    # =========================
    def _hal_for(self, idx, dtype):
        idx = idx.upper()
        halPin = CIA402_HAL.get(idx, f"obj-{idx.lower()}")
        halType = "u32" if idx in ["6040", "6041"] else "s32"
        return halPin, halType

    # =========================
    # Fixing tags
    # =========================
    def _fix_close_tags(self, xml_text):
        xml_text = xml_text.replace(" />", "/>")
        xml_text = xml_text.replace("</slave></master>", "</slave>\n </master>")
        return xml_text

    # =========================
    # Conversion
    # =========================
    def convert(self):
        if not self.esi:
            messagebox.showerror("error", "first load ESI")
            return

        s = self.esi
        o = []
        o.append("<masters>")
        o.append(' <master idx="0" appTimePeriod="1000000" refClockSyncCycles="1">')
        o.append('  <slave idx="0" type="EK1100"/>')

        o.append(
            '  <slave idx="1" type="generic" '
            f'vid="{hex8(s["vendor"])}" '
            f'pid="{hex8(s["product"])}" '
            f'configPdos="true">'
        )

        o.append('   <dcConf assignActivate="300" sync0Cycle="*1" sync0Shift="0"/>')

        o.append('   <syncManager idx="2" dir="out">')
        for pdo in s["rx"]:
            o.append(f'     <pdo idx="{pdo["index"]}">')
            for e in pdo["entries"]:
                halPin, halType = self._hal_for(e["idx"], e["dtype"])
                o.append(
                    f'       <pdoEntry idx="{e["idx"]}" subIdx="{int(e["sub"]):02}" '
                    f'bitLen="{e["bits"]}" halPin="{halPin}" halType="{halType}"/>'
                )
            o.append("     </pdo>")
        o.append("   </syncManager>")

        o.append('   <syncManager idx="3" dir="in">')
        for pdo in s["tx"]:
            o.append(f'     <pdo idx="{pdo["index"]}">')
            for e in pdo["entries"]:
                halPin, halType = self._hal_for(e["idx"], e["dtype"])
                o.append(
                    f'       <pdoEntry idx="{e["idx"]}" subIdx="{int(e["sub"]):02}" '
                    f'bitLen="{e["bits"]}" halPin="{halPin}" halType="{halType}"/>'
                )
            o.append("     </pdo>")
        o.append("   </syncManager>")

        o.append("  </slave>")
        o.append(" </master>")
        o.append("</masters>")

        xml_text = self._fix_close_tags("\n".join(o))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", xml_text)

    # =========================
    # Replace names (halPin only)
    # =========================
    def replace_names(self):
        txt = self.text.get("1.0", "end").strip()
        if not txt:
            messagebox.showerror("error", "Generate XML first")
            return

        try:
            root = ET.fromstring(txt)
        except ET.ParseError as e:
            messagebox.showerror("Błąd", f"Invalid XML: {e}")
            return

        for p in root.findall(".//pdoEntry"):
            idx = p.attrib.get("idx", "").replace("0x", "").upper()
            if idx in CUSTOM_HAL_PINS:
                p.set("halPin", CUSTOM_HAL_PINS[idx])

        xml = self._fix_close_tags(ET.tostring(root, encoding="unicode"))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", xml)

    # =========================
    # Reduce PDO to CSP essentials
    # =========================
    def reduce_pdo_csp(self):
        txt = self.text.get("1.0", "end").strip()
        if not txt:
            messagebox.showerror("error", "Generate XML first")
            return
        try:
            root = ET.fromstring(txt)
        except ET.ParseError as e:
            messagebox.showerror("error", f"Invalid XML: {e}")
            return

        keep_map = {
            "1600": ["6040", "607A", "6060"],
            "1A00": ["6041", "6064", "606C", "6061"]
        }

        for sm in root.findall(".//syncManager"):
            for pdo in list(sm.findall("pdo")):
                idx = pdo.attrib.get("idx", "").upper()
                if idx not in keep_map:
                    sm.remove(pdo)
                else:
                    for entry in list(pdo.findall("pdoEntry")):
                        if entry.attrib.get("idx", "").upper() not in keep_map[idx]:
                            pdo.remove(entry)

        xml = self._fix_close_tags(ET.tostring(root, encoding="unicode"))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", xml)

    # =========================
    # Slave duplication
    # =========================
    def duplicate_slave(self):
        txt = self.text.get("1.0", "end").strip()
        if not txt:
            messagebox.showerror("error", "Generate XML first")
            return

        root = ET.fromstring(txt)
        slaves = root.findall(".//slave")
        max_idx = max(int(s.attrib.get("idx", "0")) for s in slaves)

        slave1 = root.find(".//slave[@idx='1']")
        if slave1 is None:
            messagebox.showerror("Błąd", "Brak slave idx=1")
            return

        new_slave = ET.fromstring(ET.tostring(slave1, encoding="unicode"))
        new_slave.set("idx", str(max_idx + 1))
        root.find(".//master").append(new_slave)

        xml = self._fix_close_tags(ET.tostring(root, encoding="unicode"))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", xml)

    # =========================
    # Save
    # =========================
    def save_xml(self):
        txt = self.text.get("1.0", "end").strip()
        if not txt:
            return

        path = filedialog.asksaveasfilename(
            initialfile="ethercat-conf.xml",
            defaultextension=".xml",
            filetypes=[("XML", "*.xml"), ("All files", "*.*")]
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        messagebox.showinfo("OK", "File saved")

# =========================
if __name__ == "__main__":
    root = tk.Tk()
    ESI2LinuxCNC(root)
    root.mainloop()

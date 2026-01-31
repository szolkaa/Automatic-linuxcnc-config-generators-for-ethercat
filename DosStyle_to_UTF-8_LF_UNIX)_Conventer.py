import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

def convert_files_to_lf(file_paths):
    converted_files = []
    for file_path in file_paths:
        if not os.path.isfile(file_path):
            print(f"File does not exist: {file_path}")
            continue
        try:
            # Open the file in binary mode
            with open(file_path, "rb") as f:
                raw = f.read()

            # Replace all CRLF (\r\n) i CR (\r) na LF (\n)
            text = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

            # Save again in UTF-8
            with open(file_path, "wb") as f:
                f.write(text)

            converted_files.append(file_path)
        except Exception as e:
            print(f"Conversion failed: {file_path}")
            print(e)
    return converted_files

def add_folder(text_area):
    folder_path = filedialog.askdirectory()
    if folder_path:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                text_area.insert(tk.END, file_path.replace("\\", "/") + "\n")

def add_file(text_area):
    file_path = filedialog.askopenfilename()
    if file_path:
        text_area.insert(tk.END, file_path.replace("\\", "/") + "\n")

def convert_from_text(text_area):
    content = text_area.get("1.0", tk.END).strip()
    file_paths = [line.strip() for line in content.splitlines() if line.strip()]
    if not file_paths:
        messagebox.showinfo("Info", "No files to convert!")
        return
    converted_files = convert_files_to_lf(file_paths)
    messagebox.showinfo("Success", f"Converted {len(converted_files)} files!")

root = tk.Tk()
root.title("Converter do UTF-8 + LF")

# ScrolledText for displaying and editing paths
text_area = scrolledtext.ScrolledText(root, width=80, height=20)
text_area.pack(padx=10, pady=10)

# Buttons
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

tk.Button(button_frame, text="Add folder", command=lambda: add_folder(text_area)).grid(row=0, column=0, padx=5)
tk.Button(button_frame, text="Add file", command=lambda: add_file(text_area)).grid(row=0, column=1, padx=5)
tk.Button(button_frame, text="Convert files", command=lambda: convert_from_text(text_area)).grid(row=0, column=2, padx=5)

root.mainloop()

# -*- coding: utf-8 -*- # Specify encoding
import os
import sys
import zipfile
import shutil
import json
import re # Keep re for various tasks including layout generation
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import webbrowser
import subprocess # For running ptp_converter.exe
from datetime import datetime
import threading
import time

# --- Helper function to find resources (for PyInstaller) ---
def get_resource_path(relative_path: str) -> str:
    """ Gets the absolute path to a resource, works for development and for PyInstaller. """
    try:
        # PyInstaller creates a temporary folder and stores the path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # _MEIPASS is not defined, we are in development mode (not bundled)
        # Assume the resource is in the same directory as the main script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- Constants ---
CONFIG_DIR_NAME = ".pmdg_livery_installer"
CONFIG_FILE_NAME = "config.json"
DEFAULT_MIN_GAME_VERSION = "1.37.19" # Update as needed for MSFS version compatibility
PTP_CONVERTER_EXE_NAME = "ptp_converter.exe"

# Base folder names in Community
VARIANT_PACKAGE_MAP = {
    "200ER": "pmdg-aircraft-77er-liveries",
    "300ER": "pmdg-aircraft-77w-liveries",
    "F": "pmdg-aircraft-77f-liveries"
}

# Base aircraft folder names inside SimObjects/Airplanes (used in aircraft.cfg)
VARIANT_BASE_AIRCRAFT_MAP = {
    "200ER": "PMDG 777-200ER",
    "300ER": "PMDG 777-300ER",
    "F": "PMDG 777F"
}

# Expected PMDG package folder names in LocalState/packages (for validation)
EXPECTED_PMDG_PACKAGE_NAMES = {
    "pmdg-aircraft-77er", "pmdg-aircraft-77w", "pmdg-aircraft-77f",
    "pmdg-aircraft-737-600", "pmdg-aircraft-737-700",
    "pmdg-aircraft-737-800", "pmdg-aircraft-737-900",
}

# Map variant code to the required base PMDG package dependency name
VARIANT_DEPENDENCY_MAP = {
    "200ER": "pmdg-aircraft-77er",
    "300ER": "pmdg-aircraft-77w",
    "F": "pmdg-aircraft-77f"
}

WINDOWS_TICKS = 10000000  # 10^7
SEC_TO_UNIX_EPOCH = 11644473600

def _unix_to_filetime(unix_ts) -> int:
    """Converts a Unix timestamp to Windows FILETIME."""
    try:
        unix_ts_float = float(unix_ts)
        return int((unix_ts_float + SEC_TO_UNIX_EPOCH) * WINDOWS_TICKS)
    except (ValueError, TypeError):
        print(f"Warning: Invalid timestamp encountered: {unix_ts}. Using current time.")
        return int((time.time() + SEC_TO_UNIX_EPOCH) * WINDOWS_TICKS)

class PMDGLiveryInstaller:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.app_version = "v1.10.2" # Reflects PTP logic, UI reset, and English translation

        master.title(f"PMDG 777 Livery Installer {self.app_version}")
        master.geometry("850x750") # Adjusted for slightly longer English text in some places
        master.minsize(750, 700)

        icon_path_rel = "icon.ico"
        try:
            icon_path_abs = get_resource_path(icon_path_rel)
            if os.path.exists(icon_path_abs): master.iconbitmap(icon_path_abs)
            else: print(f"Warning: Icon file not found at {icon_path_abs}")
        except Exception as e: print(f"Warning: Could not set window icon: {e}")

        self.ptp_converter_exe = get_resource_path(PTP_CONVERTER_EXE_NAME)
        if not os.path.exists(self.ptp_converter_exe):
            print(f"CRITICAL WARNING: {PTP_CONVERTER_EXE_NAME} not found at {self.ptp_converter_exe}. "
                  "PTP functionality will be unavailable.")
            self.ptp_converter_exe = None

        self.selected_zip_files: list[str] = [] # Holds paths to .zip or .ptp

        # UI Colors
        self.bg_color = "#f0f0f0"
        self.header_bg = "#1a3f5c"
        self.header_fg = "white"
        self.button_color = "#2c5f8a"
        self.button_hover = "#3d7ab3"
        self.accent_color = "#007acc"
        self.success_color = "dark green"
        self.warning_color = "orange"
        self.error_color = "red"

        # UI Styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Header.TFrame", background=self.header_bg)
        self.style.configure("TButton", padding=8, relief="flat", background=self.button_color, foreground="white", font=("Arial", 10), borderwidth=0)
        self.style.map("TButton", background=[("active", self.button_hover)])
        self.style.configure("Accent.TButton", font=("Arial", 11, "bold"))
        self.style.configure("TLabel", background=self.bg_color, padding=6, font=("Arial", 10))
        self.style.configure("Header.TLabel", font=("Arial", 14, "bold"), foreground=self.header_fg, background=self.header_bg)
        self.style.configure("Subheader.TLabel", font=("Arial", 12, "bold"), foreground=self.header_bg)
        self.style.configure("Info.TLabel", font=("Arial", 9, "italic"), foreground="#555555")
        self.style.configure("Warn.Info.TLabel", font=("Arial", 9, "italic"), foreground=self.warning_color)
        self.style.configure("Status.TLabel", font=("Arial", 10))
        self.style.configure("TLabelframe", padding=5, background=self.bg_color)
        self.style.configure("TLabelframe.Label", font=("Arial", 10, "bold"), foreground=self.header_bg, background=self.bg_color)
        self.style.configure("Horizontal.TProgressbar", thickness=20, background=self.accent_color, troughcolor='#e0e0e0')
        self.style.configure("TRadiobutton", background=self.bg_color, font=("Arial", 10))
        self.style.configure("TNotebook", background=self.bg_color)
        self.style.configure("TNotebook.Tab", padding=[10, 5], font=("Arial", 10))

        # Main Container
        main_container = ttk.Frame(master, style="TFrame")
        main_container.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_container, style="Header.TFrame")
        header_frame.pack(fill=tk.X)
        title_frame = ttk.Frame(header_frame, style="Header.TFrame")
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)
        ttk.Label(title_frame, text="PMDG 777 Livery Installation Tool", style="Header.TLabel").pack(side=tk.TOP, anchor=tk.W)
        ttk.Label(title_frame, text="Install custom liveries and generate layout for PMDG 777", foreground="light gray", background=self.header_bg, font=("Arial", 10)).pack(side=tk.TOP, anchor=tk.W, pady=(0, 5))

        # Main Frame for Notebook
        self.main_frame = ttk.Frame(main_container, padding="20", style="TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(self.main_frame, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Tabs
        setup_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(setup_tab, text="  Setup  ") # English
        install_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(install_tab, text="  Install Livery(s)  ") # English
        help_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(help_tab, text="  Help  ") # English

        # Initialize tab content
        self._setup_setup_tab(setup_tab)
        self._setup_install_tab(install_tab)
        self._setup_help_tab(help_tab)

        # Status Bar
        status_frame = ttk.Frame(main_container, relief=tk.SUNKEN, borderwidth=1)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="Ready") # English
        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W, background='').pack(side=tk.LEFT, padx=10, pady=3)
        ttk.Label(status_frame, text=self.app_version, style="Status.TLabel", anchor=tk.E, background='').pack(side=tk.RIGHT, padx=10, pady=3)

        self.load_config()
        master.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_setup_tab(self, parent: ttk.Frame):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Configuration Settings", style="Subheader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15)) # English

        # Community Folder
        ttk.Label(parent, text="MSFS Community Folder:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.community_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.community_path_var, width=60).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Button(parent, text="Browse...", command=self.select_community_folder).grid(row=1, column=2, padx=5, pady=5) # English
        ttk.Label(parent, text="Location of your MSFS add-ons (Community folder).", style="Info.TLabel").grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=5) # English
        ttk.Button(parent, text="Find Common Locations", command=self.show_common_locations).grid(row=2, column=0, sticky=tk.W, padx=5) # English

        # PMDG Package Paths (LocalState)
        pmdg_path_frame = ttk.LabelFrame(parent, text="PMDG Package Paths (for .ini files)", padding=10) # English
        pmdg_path_frame.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(20, 5))
        pmdg_path_frame.columnconfigure(1, weight=1)
        
        self.pmdg_77er_path_var = tk.StringVar() # Initialize here
        self.pmdg_77w_path_var = tk.StringVar()
        self.pmdg_77f_path_var = tk.StringVar()
        
        paths_to_setup = [
            ("777-200ER Path:", self.pmdg_77er_path_var, "pmdg-aircraft-77er"), # English
            ("777-300ER Path:", self.pmdg_77w_path_var, "pmdg-aircraft-77w"), # English
            ("777F Path:", self.pmdg_77f_path_var, "pmdg-aircraft-77f"),       # English
        ]
        for i, (label_text, var, expected_prefix) in enumerate(paths_to_setup):
            ttk.Label(pmdg_path_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(pmdg_path_frame, textvariable=var, width=55).grid(row=i, column=1, sticky=tk.EW, pady=5)
            ttk.Button(pmdg_path_frame, text="Browse...", command=lambda v=var, p=expected_prefix: self.select_pmdg_package_folder(v, p)).grid(row=i, column=2, padx=5, pady=5) # English
        
        ttk.Label(pmdg_path_frame, text="Path to the specific PMDG aircraft package folder (e.g., pmdg-aircraft-77er) within '...\\LocalState\\packages'.", style="Info.TLabel").grid(row=len(paths_to_setup), column=1, columnspan=2, sticky=tk.W, padx=5, pady=(5,0)) # English

        # Reference Livery Folder
        ttk.Label(parent, text="Reference 777 Livery Folder:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # English
        self.reference_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.reference_path_var, width=60).grid(row=4, column=1, sticky=tk.EW, pady=(20, 5))
        ttk.Button(parent, text="Browse...", command=self.select_reference_folder).grid(row=4, column=2, padx=5, pady=(20, 5)) # English
        ttk.Label(parent, text="Any installed PMDG 777 livery folder (for manifest/layout templates).", style="Info.TLabel").grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=5) # English

        # Save Button
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=3, sticky=tk.EW, pady=25)
        ttk.Button(parent, text="Save Settings", command=self.save_config).grid(row=7, column=0, columnspan=3, pady=10) # English

    def _setup_install_tab(self, parent: ttk.Frame):
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(8, weight=1) # Log area expansion

        ttk.Label(parent, text="Install New Livery(s)", style="Subheader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15)) # English
        ttk.Label(parent, text="Livery File(s):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.livery_zip_display_var = tk.StringVar()
        self.livery_zip_entry = ttk.Entry(parent, textvariable=self.livery_zip_display_var, width=60, state='readonly')
        self.livery_zip_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Button(parent, text="Browse...", command=self.select_livery_files).grid(row=1, column=2, padx=5, pady=5) # English
        ttk.Label(parent, text="Select one or more archive files (.zip or .ptp).", style="Info.TLabel").grid(row=2, column=1, sticky=tk.W, padx=5) # English
        ttk.Label(parent, text="IMPORTANT! If selecting multiple files, they MUST be for the SAME aircraft variant.", style="Warn.Info.TLabel").grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=5) # English

        ttk.Label(parent, text="Aircraft Variant:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # English
        self.aircraft_variant_var = tk.StringVar()
        variant_frame = ttk.Frame(parent, style="TFrame")
        variant_frame.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=(20, 5))
        ttk.Radiobutton(variant_frame, text="777-200ER", variable=self.aircraft_variant_var, value="200ER").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(variant_frame, text="777-300ER", variable=self.aircraft_variant_var, value="300ER").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(variant_frame, text="777F", variable=self.aircraft_variant_var, value="F").pack(side=tk.LEFT)
        ttk.Label(parent, text="You must select an aircraft variant.", style="Info.TLabel").grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=5) # English

        ttk.Label(parent, text="Livery Name (in-sim):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # English
        self.custom_name_var = tk.StringVar()
        self.custom_name_entry = ttk.Entry(parent, textvariable=self.custom_name_var, width=60)
        self.custom_name_entry.grid(row=6, column=1, sticky=tk.EW, pady=(20, 5))
        ttk.Label(parent, text="Optional. Ignored if multiple files selected (will be auto-detected).", style="Info.TLabel").grid(row=7, column=1, columnspan=2, sticky=tk.W, padx=5) # English

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=8, column=0, columnspan=3, sticky=tk.EW, pady=25)
        
        action_frame = ttk.Frame(parent, style="TFrame")
        action_frame.grid(row=9, column=0, columnspan=3, sticky=tk.NSEW, pady=10)
        action_frame.columnconfigure(0, weight=1)
        action_frame.rowconfigure(2, weight=1) 

        self.install_button = ttk.Button(action_frame, text="Install Livery(s) & Generate Layout", command=self.start_install_thread, style="Accent.TButton") # English
        self.install_button.grid(row=0, column=0, pady=(0, 15))

        progress_frame = ttk.Frame(action_frame, style="TFrame")
        progress_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        progress_frame.columnconfigure(1, weight=1)
        ttk.Label(progress_frame, text="Progress:").grid(row=0, column=0, sticky=tk.W) # English
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, style="Horizontal.TProgressbar")
        self.progress.grid(row=0, column=1, sticky=tk.EW, padx=5)

        log_frame = ttk.LabelFrame(action_frame, text="Installation Log", style="TLabelframe") # English
        log_frame.grid(row=2, column=0, sticky=tk.NSEW)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=12, width=80, wrap=tk.WORD, bd=0, font=("Courier New", 9), relief=tk.FLAT, background="white")
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=(0,5), pady=5)
        self.log_text.config(yscrollcommand=scrollbar.set, state=tk.DISABLED)
        
        for tag, color, is_bold in [
            ("SUCCESS", self.success_color, False), ("WARNING", self.warning_color, False),
            ("ERROR", self.error_color, True), ("STEP", self.header_bg, True),
            ("DETAIL", "#555555", False), ("CMD", "purple", True)
        ]:
            font_options = ("Courier New", 9, "bold" if is_bold else "normal")
            if tag == "CMD": font_options = ("Courier New", 9, "italic")
            self.log_text.tag_configure(tag, foreground=color, font=font_options)
        self.log_text.tag_configure("INFO", foreground="black", font=("Courier New", 9))

    def _setup_help_tab(self, parent: ttk.Frame):
        help_canvas = tk.Canvas(parent, highlightthickness=0, background=self.bg_color)
        help_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=help_canvas.yview)
        scrollable_frame = ttk.Frame(help_canvas, style="TFrame")
        
        scrollable_frame.bind("<Configure>", lambda e: help_canvas.configure(scrollregion=help_canvas.bbox("all")))
        canvas_window = help_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        help_canvas.configure(yscrollcommand=help_scrollbar.set)
        
        def rebind_wraplength(event): # Closure to update wraplengths
            width = event.width 
            for child in scrollable_frame.winfo_children():
                if isinstance(child, ttk.Label) and hasattr(child, '_original_indent'):
                    indent_pixels = child._original_indent * 20
                    child.config(wraplength=max(100, width - indent_pixels - 30)) 

        scrollable_frame.bind('<Configure>', rebind_wraplength) 
        help_canvas.bind('<Configure>', lambda e: help_canvas.itemconfig(canvas_window, width=e.width))

        help_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        help_scrollbar.pack(side="right", fill="y", padx=(0,5), pady=5)

        current_row = 0
        
        def add_section_header(text):
            nonlocal current_row
            lbl = ttk.Label(scrollable_frame, text=text, style="Subheader.TLabel")
            lbl.grid(row=current_row, column=0, sticky="w", pady=(15, 5)); lbl._original_indent = 0
            current_row += 1
        
        def add_text(text, indent=0, style="TLabel"):
            nonlocal current_row
            lbl = ttk.Label(scrollable_frame, text=text, justify=tk.LEFT, style=style, background=self.bg_color)
            lbl.grid(row=current_row, column=0, sticky="w", padx=(indent * 20, 0)); lbl._original_indent = indent
            current_row += 1
        
        def add_bold_text(text, indent=0):
            nonlocal current_row
            lbl = ttk.Label(scrollable_frame, text=text, justify=tk.LEFT, font=("Arial", 10, "bold"), background=self.bg_color)
            lbl.grid(row=current_row, column=0, sticky="w", padx=(indent * 20, 0), pady=(5,0)); lbl._original_indent = indent
            current_row += 1

        # --- Help Content (English) ---
        add_section_header("Quick Start Guide")
        add_text("1. Go to the Setup tab:")
        add_text("- Select your MSFS Community folder.", indent=1)
        add_text("- Set the 'PMDG Package Path' for each 777 variant you own (important for .ini files). Point to the specific PMDG aircraft folder (e.g., pmdg-aircraft-77er) inside ...\\LocalState\\packages.", indent=1)
        add_text("- Select any existing installed PMDG 777 livery folder as a Reference.", indent=1)
        add_text("- Click Save Settings.", indent=1)
        add_text("2. Go to the Install Livery(s) tab:")
        add_text("- Browse for your livery archive file(s) (.zip or .ptp).", indent=1)
        add_text("- IMPORTANT! Choose the correct Aircraft Variant (777-200ER, 777-300ER, or 777F). This is mandatory!", indent=1)
        add_text("- If selecting multiple files, ensure ALL are for the same variant you chose.", indent=1)
        add_text("- Optionally, enter a Livery Name if you selected a SINGLE file.", indent=1)
        add_text("- Click 'Install Livery(s) & Generate Layout'.", indent=1)
        add_text("3. Check the log for success or errors. The tool will copy files, modify aircraft.cfg, handle .ini files, and automatically generate layout.json.", indent=1)
        add_text("4. Launch MSFS and find your new livery/liveries! (Restart MSFS if it was running).", indent=1)

        add_section_header("Configuration Details")
        add_bold_text("MSFS Community Folder:")
        add_text("This is where MSFS add-ons are installed.", indent=1)
        add_bold_text("PMDG Package Paths (LocalState):")
        add_text("Path to the specific PMDG aircraft package folder (e.g., 'pmdg-aircraft-77er') inside the 'packages' folder in your MSFS LocalState. Used for copying renamed .ini files.", indent=1)
        add_bold_text("Reference 777 Livery Folder:")
        add_text("Needed for copying manifest.json and layout.json templates if the livery package is new.", indent=1)
        add_bold_text(f"{PTP_CONVERTER_EXE_NAME}:")
        add_text(f"This tool requires '{PTP_CONVERTER_EXE_NAME}' to process .ptp files. Ensure it is in the same folder as this livery installer.", indent=1)
        add_text("If missing, .ptp file installation will fail.", indent=1)
        add_bold_text("Long File Path Handling (Windows):")
        add_text("MSFS and its add-ons can use very long file paths. To ensure this tool can correctly scan all livery files, "
                 "especially during 'layout.json' generation, enabling 'Win32 long paths' in your Windows OS is recommended.", indent=1)
        add_text("Search online for 'Enable Win32 long paths Windows 10/11' for instructions. This application is also packaged to be long-path aware.", indent=1)
        add_section_header("Troubleshooting") # English
        add_bold_text("Livery Not Appearing in MSFS:") # English
        add_text("- Check the Installation Log for ERROR messages, especially during 'Generating layout.json' or 'Processing options.ini' steps.", indent=1) # English
        add_text("- Verify that the MSFS Community Folder path is correct in Setup.", indent=1) # English
        add_text("- Ensure you selected the correct Aircraft Variant during installation.", indent=1) # English
        add_text("- Ensure the dependency in the package's manifest.json (e.g., in pmdg-aircraft-77w-liveries) matches the base aircraft (e.g., 'pmdg-aircraft-77w'). The tool attempts to fix this, but check the log.", indent=1) # English
        add_text("- For 777-200ER, check the log if the correct engine type (GE/RR/PW) was detected and applied to aircraft.cfg.", indent=1) # English
        add_text("- Verify the 'PMDG Package Path (LocalState)' for the relevant variant is correct if you expected an .ini file to be copied.", indent=1) # English
        add_text("- Restart MSFS. A restart is sometimes needed.", indent=1) # English
        add_text("- Check the MSFS Content Manager for the livery package.", indent=1) # English
        add_text("- If layout generation failed or was skipped (see log), new liveries won't appear until this step completes successfully for the entire batch.", indent=1) # English

        add_bold_text("Installation Errors:") # English
        add_text("- Ensure the archive file(s) (.zip or .ptp) are not corrupt. ZIPs should contain expected folders (texture.*, model, aircraft.cfg, optionally options.ini or <atc_id>.ini).", indent=1) # English
        add_text(f"- For .ptp files, ensure {PTP_CONVERTER_EXE_NAME} is functional and in the same folder as this application.", indent=1) # English
        add_text("- Verify the selected Reference Livery Folder is valid and functional.", indent=1) # English
        
        add_bold_text("Nested ZIPs:") # English
        add_text("- The tool attempts to detect and install liveries from ZIP files contained within a primary selected ZIP file (e.g., a 'pack' zip).", indent=1) # English
        add_text("- Check the log if a 'pack' file fails; it might indicate an unexpected internal structure.", indent=1) # English
        
        add_bold_text("RAR Files:") # English
        add_text("- This tool only supports ZIP and PTP (via ptp_converter.exe) archive files.", indent=1) # English

        add_section_header("About") # English
        add_text(f"PMDG 777 Livery Installer {self.app_version}")
        add_text("This tool prepares, copies, and configures livery files for the PMDG 777 family in MSFS.", style="TLabel") # English
        add_text(f"It handles folder creation, file extraction (ZIPs, including nested; PTPs using {PTP_CONVERTER_EXE_NAME}), " 
                 "aircraft.cfg modification, options.ini/<atc_id>.ini handling, and automatically generates "
                 "layout.json and updates manifest.json.", style="TLabel") # English
        add_text("Disclaimer: Use at your own risk. Not affiliated with PMDG or Microsoft.", style="Info.TLabel") # English

        # Force an initial configure event to set initial wraplengths for help text
        parent.update_idletasks() 
        for child in scrollable_frame.winfo_children():
            if isinstance(child, ttk.Label) and hasattr(child, '_original_indent'):
                indent_pixels = child._original_indent * 20
                # Use scrollable_frame.winfo_width() as it's the container for these labels
                child.config(wraplength=max(100, scrollable_frame.winfo_width() - indent_pixels - 30))


    def show_common_locations(self):
        common_locations = """Common MSFS Community Folder Locations:

NOTE: [YourUserName] should be replaced with your actual Windows username.

Microsoft Store Version:
C:\\Users\\[YourUserName]\\AppData\\Local\\Packages\\Microsoft.FlightSimulator_8wekyb3d8bbwe\\LocalCache\\Packages\\Community

Steam Version:
C:\\Users\\[YourUserName]\\AppData\\Roaming\\Microsoft Flight Simulator\\Packages\\Community

Custom Installation Drive (Example D:):
D:\\MSFS\\Community (If you chose a custom path during MSFS installation)

Xbox App / PC Game Pass (May Vary):
Check drive settings under the Xbox app, often involves hidden/protected folders like 'WpSystem' or 'WindowsApps'. Access might be restricted. Using Store/Steam paths is more common for PC users.

Finding AppData:
Press Windows Key + R, type `%appdata%` and press Enter to open the Roaming folder.
Press Windows Key + R, type `%localappdata%` and press Enter to open the Local folder.
""" # English
        location_window = tk.Toplevel(self.master)
        location_window.title("Common Community Folder Locations") # English
        location_window.geometry("700x400")
        location_window.resizable(False, False)
        location_window.transient(self.master)
        location_window.grab_set()

        win_frame = ttk.Frame(location_window, padding=10, style="TFrame")
        win_frame.pack(fill=tk.BOTH, expand=True)
        text_widget = tk.Text(win_frame, wrap=tk.WORD, padx=15, pady=15, bd=0, relief=tk.FLAT, font=("Arial", 10), background=self.bg_color)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, common_locations)
        text_widget.config(state=tk.DISABLED)
        btn_frame = ttk.Frame(win_frame, padding=(0, 10, 0, 0), style="TFrame")
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Copy Info to Clipboard", command=lambda: self.copy_to_clipboard(common_locations, location_window)).pack(side=tk.LEFT, padx=5) # English
        ttk.Button(btn_frame, text="Close", command=location_window.destroy).pack(side=tk.RIGHT, padx=5) # English
        location_window.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (location_window.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (location_window.winfo_height() // 2)
        location_window.geometry(f'+{x}+{y}')

    def copy_to_clipboard(self, text: str, parent_window: tk.Toplevel):
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
            self.master.update()
            messagebox.showinfo("Copied", "Locations copied to clipboard.", parent=parent_window) # English
        except tk.TclError:
            messagebox.showwarning("Clipboard Error", "Could not access the clipboard.", parent=parent_window) # English

    def log(self, message: str, level: str = "INFO"):
        if threading.current_thread() is not threading.main_thread():
            self.master.after(0, self.log, message, level)
            return
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            prefix = f"[{timestamp}] [{level.upper()}] "
            tag_to_use = level.upper() if level.upper() in self.log_text.tag_names() else "INFO"
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, prefix + message + "\n", tag_to_use)
            self.log_text.config(state=tk.DISABLED)
            self.log_text.see(tk.END)
        except Exception as e:
            print(f"Error logging message: {e}") 

    def select_community_folder(self):
        current_path = self.community_path_var.get()
        initial_dir = current_path if Path(current_path).is_dir() else str(Path.home())
        folder = filedialog.askdirectory(title="Select MSFS Community Folder", initialdir=initial_dir) # English
        if folder:
            self.community_path_var.set(folder)
            self.log(f"Community Folder selected: {folder}", "DETAIL") # English

    def _get_parent_localstate_packages_path(self) -> Path | None:
        try:
            local_app_data = os.getenv('LOCALAPPDATA')
            if local_app_data:
                packages_dir = Path(local_app_data) / "Packages"
                if packages_dir.is_dir():
                    msfs_pkg_pattern = "Microsoft.FlightSimulator_*_8wekyb3d8bbwe"
                    for item in packages_dir.iterdir():
                        if item.is_dir() and re.match(msfs_pkg_pattern, item.name, re.IGNORECASE):
                            potential_path = item / "LocalState" / "packages"
                            if potential_path.is_dir(): return potential_path
            app_data = os.getenv('APPDATA')
            if app_data:
                steam_msfs_packages_path = Path(app_data) / "Microsoft Flight Simulator" / "Packages"
                if steam_msfs_packages_path.is_dir():
                    return steam_msfs_packages_path.parent 
        except Exception as e:
            self.log(f"Error trying to auto-detect LocalState packages path: {e}", "DEBUG") # English
        return Path.home()

    def select_pmdg_package_folder(self, target_var: tk.StringVar, expected_folder_prefix: str):
        initial_dir_guess = self._get_parent_localstate_packages_path() or Path.home()
        folder = filedialog.askdirectory(
            title=f"Select PMDG Package Folder (e.g., {expected_folder_prefix}) in ...LocalState\\packages", # English
            initialdir=str(initial_dir_guess)
        )
        if folder:
            p_folder = Path(folder)
            folder_name_lower = p_folder.name.lower()
            if folder_name_lower in EXPECTED_PMDG_PACKAGE_NAMES:
                if folder_name_lower == expected_folder_prefix.lower():
                    # More lenient check: ensure it's inside a 'packages' folder, which is inside 'LocalState'
                    if p_folder.parent and p_folder.parent.name.lower() == 'packages' and \
                       p_folder.parent.parent and p_folder.parent.parent.name.lower() == 'localstate':
                        target_var.set(str(p_folder))
                        self.log(f"PMDG Package Path ({expected_folder_prefix}) set: {p_folder}", "DETAIL") # English
                    else:
                        messagebox.showwarning("Potential Incorrect Path", # English
                                             f"The folder '{p_folder.name}' is a valid PMDG package, "
                                             f"but it does not appear to be inside a '...\\LocalState\\packages' structure.\n\n"
                                             f"Please ensure this is the correct path.")
                        target_var.set(str(p_folder))
                        self.log(f"PMDG Package Path ({expected_folder_prefix}) set (Warning: verify 'LocalState\\packages' structure): {p_folder}", "WARNING") # English
                else:
                    messagebox.showerror("Incorrect Variant", # English
                                         f"You selected the folder '{p_folder.name}', but a folder like '{expected_folder_prefix}' was expected.\n\n"
                                         f"Please select the correct PMDG package folder for this variant.")
                    self.log(f"Incorrect PMDG package variant selected for {expected_folder_prefix}. Selected: {folder}", "ERROR") # English
            else:
                messagebox.showerror("Invalid Folder", # English
                                     f"The selected folder '{p_folder.name}' does not appear to be a valid PMDG package folder (e.g., {expected_folder_prefix}).\n\n"
                                     f"Please select the correct folder within '...\\LocalState\\packages'.")
                self.log(f"Invalid PMDG Package Path selected: {folder}", "ERROR") # English

    def select_reference_folder(self):
        current_path = self.reference_path_var.get()
        initial_dir = current_path if Path(current_path).is_dir() else \
                      (self.community_path_var.get() if Path(self.community_path_var.get()).is_dir() else str(Path.home()))
        folder = filedialog.askdirectory(title="Select Reference PMDG 777 Livery Folder", initialdir=initial_dir) # English
        if folder:
            p_folder = Path(folder)
            if (p_folder / "manifest.json").is_file() and (p_folder / "layout.json").is_file():
                self.reference_path_var.set(str(p_folder))
                self.log(f"Reference livery folder selected: {p_folder}", "DETAIL") # English
            else:
                missing = [f_name for f_name in ["manifest.json", "layout.json"] if not (p_folder / f_name).is_file()]
                messagebox.showwarning("Invalid Reference", f"The selected folder is missing: {', '.join(missing)}.") # English
                self.log(f"Invalid reference folder (missing {', '.join(missing)}): {p_folder}", "WARNING") # English

    def select_livery_files(self):
        initial_dir = str(Path.home() / "Downloads") if (Path.home() / "Downloads").is_dir() else str(Path.home())
        files = filedialog.askopenfilenames(
            title="Select Livery Archive File(s) (.zip or .ptp)", # English
            filetypes=[
                ("Supported Livery Archives", "*.zip *.ptp"), ("ZIP archives", "*.zip"), # English
                ("PMDG PTP files", "*.ptp"), ("All files", "*.*")
            ], initialdir=initial_dir
        )
        if files:
            self.selected_zip_files = list(files)
            num_files = len(self.selected_zip_files)
            if num_files == 1:
                display_text = Path(self.selected_zip_files[0]).name
                self.custom_name_entry.config(state=tk.NORMAL)
                self.log(f"Livery file selected: {display_text}", "DETAIL") # English
                if not self.custom_name_var.get() and \
                   (display_text.lower().endswith((".zip", ".ptp"))):
                    base_name = Path(display_text).stem
                    clean_name = re.sub(r'^(pmdg[-_]?)?(777[-_]?(200er|300er|f|w)?[-_]?)', '', base_name, flags=re.IGNORECASE).strip('-_ ')
                    clean_name = ' '.join(re.sub(r'[-_]+', ' ', clean_name).split()).strip()
                    clean_name = ' '.join(word.capitalize() for word in clean_name.split()) if clean_name else "Unnamed Livery" # English
                    if clean_name:
                        self.custom_name_var.set(clean_name)
                        self.log(f"Suggested livery name: {clean_name}", "DETAIL") # English
            else:
                display_text = f"[{num_files} files selected]" # English
                self.custom_name_var.set("")
                self.custom_name_entry.config(state=tk.DISABLED)
                self.log(f"{num_files} livery files selected.", "INFO") # English
            self.livery_zip_display_var.set(display_text)
        else:
            self.selected_zip_files = []
            self.livery_zip_display_var.set("")
            self.custom_name_entry.config(state=tk.NORMAL)
            self.log("Livery file selection cancelled.", "DETAIL") # English

    def save_config(self):
        config = {
            "community_path": self.community_path_var.get(),
            "reference_path": self.reference_path_var.get(),
            "pmdg_77er_path": self.pmdg_77er_path_var.get(),
            "pmdg_77w_path": self.pmdg_77w_path_var.get(),
            "pmdg_77f_path": self.pmdg_77f_path_var.get()
        }
        try:
            config_dir = Path.home() / CONFIG_DIR_NAME
            config_dir.mkdir(parents=True, exist_ok=True)
            with open(config_dir / CONFIG_FILE_NAME, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            self.log("Configuration saved successfully.", "SUCCESS") # English
            self.status_var.set("Configuration saved") # English
            self.master.after(2000, lambda: self.status_var.set("Ready")) # English
        except Exception as e:
            self.log(f"Error saving configuration: {str(e)}", "ERROR") # English
            messagebox.showerror("Configuration Error", f"Could not save configuration:\n{e}") # English

    def load_config(self):
        config_path = Path.home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        if config_path.exists():
            try:
                with open(config_path, "r", encoding='utf-8') as f: config = json.load(f)
                self.community_path_var.set(config.get("community_path", ""))
                self.reference_path_var.set(config.get("reference_path", ""))
                self.pmdg_77er_path_var.set(config.get("pmdg_77er_path", ""))
                self.pmdg_77w_path_var.set(config.get("pmdg_77w_path", ""))
                self.pmdg_77f_path_var.set(config.get("pmdg_77f_path", ""))
                self.log("Configuration loaded.", "INFO") # English
            except json.JSONDecodeError as e:
                self.log(f"Error decoding configuration file: {e}. Please review or delete: {config_path}", "ERROR") # English
                messagebox.showerror("Configuration Error", f"Could not load configuration (invalid JSON):\n{config_path}\nError: {e}") # English
            except Exception as e:
                self.log(f"Unknown error loading configuration: {e}", "WARNING") # English
        else:
            self.log("Configuration file not found. Please configure paths in the Setup tab.", "INFO") # English

    def get_livery_name(self, archive_path_or_folder: Path, temp_extract_dir: Path | None) -> str:
        # temp_extract_dir is the folder where aircraft.cfg is expected after PTP reorg or ZIP extract
        if temp_extract_dir and temp_extract_dir.is_dir():
            try:
                cfg_path_str = self.find_file_in_dir(temp_extract_dir, "aircraft.cfg")
                if cfg_path_str and Path(cfg_path_str).is_file():
                    with open(cfg_path_str, 'r', encoding='utf-8', errors='ignore') as cfg_file:
                        content = cfg_file.read()
                        fltsim_match = re.search(r'\[FLTSIM\.0\].*?title\s*=\s*"(.*?)"', content, re.DOTALL | re.IGNORECASE)
                        if fltsim_match and fltsim_match.group(1).strip():
                            title = fltsim_match.group(1).strip()
                            self.log(f"Name detected from aircraft.cfg [FLTSIM.0]: {title}", "INFO") # English
                            return title
                        simple_match = re.search(r'^\s*title\s*=\s*"(.*?)"', content, re.MULTILINE | re.IGNORECASE)
                        if simple_match and simple_match.group(1).strip():
                            title = simple_match.group(1).strip()
                            self.log(f"Name detected from aircraft.cfg (generic 'title='): {title}", "INFO") # English
                            return title
                else: self.log(f"aircraft.cfg not found in '{temp_extract_dir}' for name detection.", "DETAIL") # English
            except Exception as e: self.log(f"Could not read aircraft.cfg for name detection from '{temp_extract_dir}': {e}", "WARNING") # English
        
        default_name = Path(archive_path_or_folder).stem
        clean_name = re.sub(r'^(pmdg[-_]?)?(777[-_]?(200er|300er|f|w)?[-_]?)', '', default_name, flags=re.IGNORECASE).strip('-_ ')
        clean_name = ' '.join(re.sub(r'[-_]+', ' ', clean_name).split()).strip()
        clean_name = ' '.join(word.capitalize() for word in clean_name.split()) if clean_name else "Unnamed Livery" # English
        self.log(f"Using file/folder name '{default_name}' as basis for livery name: {clean_name}", "INFO") # English
        return clean_name

    def extract_atc_id(self, cfg_path: Path) -> str | None:
        if not cfg_path.is_file():
            self.log(f"extract_atc_id: File not found: {cfg_path}", "WARNING") # English
            return None
        try:
            with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            fltsim0_match = re.search(r'\[fltsim\.0\](.*?)(\n\s*\[|$)', content, re.DOTALL | re.IGNORECASE)
            if fltsim0_match:
                section_content = fltsim0_match.group(1)
                atc_id_match = re.search(r'^\s*atc_id\s*=\s*"?([a-zA-Z0-9_.\- ]+)"?', section_content, re.MULTILINE | re.IGNORECASE)
                if atc_id_match:
                    atc_id = atc_id_match.group(1).strip()
                    if atc_id:
                        safe_atc_id = re.sub(r'[\\/*?:"<>|]', '_', atc_id)
                        if safe_atc_id != atc_id: self.log(f"ATC ID '{atc_id}' sanitized to '{safe_atc_id}' for filename.", "DETAIL") # English
                        if not safe_atc_id: self.log(f"ATC ID '{atc_id}' became empty after sanitization.", "WARNING"); return None # English
                        self.log(f"Found ATC ID in [fltsim.0]: '{safe_atc_id}'", "DETAIL") # English
                        return safe_atc_id
                    else: self.log("Found ATC ID in [fltsim.0] but it is empty.", "WARNING") # English
                else: self.log("'atc_id=' line not found within [fltsim.0] section.", "WARNING") # English
            else: self.log(f"[fltsim.0] section not found in {cfg_path.name}.", "WARNING") # English
        except Exception as e: self.log(f"Error extracting ATC ID from {cfg_path}: {e}", "ERROR") # English
        return None

    def verify_settings(self) -> list[str]:
        community_path = self.community_path_var.get()
        reference_path = self.reference_path_var.get()
        pmdg_paths_vars = {
            "200ER": self.pmdg_77er_path_var.get(),
            "300ER": self.pmdg_77w_path_var.get(),
            "F": self.pmdg_77f_path_var.get()
        }
        livery_files_selected = self.selected_zip_files
        aircraft_variant = self.aircraft_variant_var.get()
        errors = []

        if not community_path: errors.append("- MSFS Community Folder path not set.") # English
        elif not Path(community_path).is_dir(): errors.append(f"- Community Folder does not exist or is not a directory:\n  {community_path}") # English

        for var_code, path_str, expected_name in [
            ("200ER", pmdg_paths_vars["200ER"], "pmdg-aircraft-77er"),
            ("300ER", pmdg_paths_vars["300ER"], "pmdg-aircraft-77w"),
            ("F", pmdg_paths_vars["F"], "pmdg-aircraft-77f")
        ]:
            if not path_str: errors.append(f"- PMDG {var_code} Package Path (LocalState) not set.") # English
            elif not Path(path_str).is_dir(): errors.append(f"- PMDG {var_code} Package Path (LocalState) is not a valid directory:\n  {path_str}") # English
            elif Path(path_str).name.lower() != expected_name: errors.append(f"- PMDG {var_code} Package folder name should be '{expected_name}'.\n  Found: {Path(path_str).name}") # English

        if not reference_path: errors.append("- Reference Livery Folder path not set.") # English
        elif not Path(reference_path).is_dir(): errors.append(f"- Reference Livery Folder does not exist or is not a directory:\n  {reference_path}") # English
        elif not (Path(reference_path) / "manifest.json").is_file(): errors.append(f"- Reference Livery Folder is missing manifest.json:\n  {reference_path}") # English
        elif not (Path(reference_path) / "layout.json").is_file(): errors.append(f"- Reference Livery Folder is missing layout.json:\n  {reference_path}") # English

        if not aircraft_variant: errors.append("- You must select an Aircraft Variant.") # English

        if not livery_files_selected:
            errors.append("- No livery archive files (.zip or .ptp) selected.") # English
        else:
            contains_ptp = any(Path(f).suffix.lower() == ".ptp" for f in livery_files_selected) # Use Path for suffix
            if contains_ptp and (not self.ptp_converter_exe or not os.path.exists(self.ptp_converter_exe)):
                 errors.append(f"- A .ptp file was selected, but '{PTP_CONVERTER_EXE_NAME}' was not found.") # English
                 errors.append(f"  Ensure '{PTP_CONVERTER_EXE_NAME}' is in the same folder as this application.") # English

            for file_path_str in livery_files_selected:
                file_p = Path(file_path_str) # Use a different variable name
                if not file_p.is_file():
                    errors.append(f"- Selected livery file does not exist:\n  {file_path_str}") # English
                elif not (file_p.suffix.lower() in [".zip", ".ptp"]):
                    errors.append(f"- File '{file_p.name}' is not a supported format (.zip or .ptp).") # English
        return errors

    def find_file_in_dir(self, directory: Path, filename_lower: str) -> str | None:
        """Recursively searches for a file (case-insensitive) in a directory."""
        search_path = Path(directory)
        if not search_path.is_dir():
            self.log(f"find_file_in_dir: Provided directory does not exist or is invalid: {search_path}", "WARNING") # English
            return None
            
        for root, dirs, files in os.walk(search_path):
            for file_name in files:
                if file_name.lower() == filename_lower:
                    return os.path.join(root, file_name)
        return None

    def find_dir_in_dir(self, directory: Path, dirname_lower: str) -> str | None:
        """Recursively searches for a directory (case-insensitive) in a directory."""
        search_dir = Path(directory)
        if not search_dir.is_dir():
            self.log(f"find_dir_in_dir: Provided directory does not exist or is invalid: {search_dir}", "WARNING") # English
            return None

        for item in search_dir.iterdir(): # Check top level first
            if item.is_dir() and item.name.lower() == dirname_lower:
                return str(item)
        
        for root, dirs, files in os.walk(search_dir, topdown=True):
            for d_name in list(dirs): 
                if d_name.lower() == dirname_lower:
                    found_path = Path(root) / d_name
                    if found_path.is_dir(): # Double check it's a directory
                        return str(found_path)
        return None

    def find_texture_dirs_in_dir(self, directory: Path) -> list[str]:
        """Finds all directories starting with 'texture.' (case-insensitive) at any level."""
        texture_dirs = []
        search_dir = Path(directory)
        if not search_dir.is_dir():
            self.log(f"find_texture_dirs_in_dir: Provided directory does not exist or is invalid: {search_dir}", "WARNING") # English
            return []
            
        try:
            for root_str, dirs, files in os.walk(search_dir): # os.walk yields str for root
                root_path = Path(root_str)
                for d_name in list(dirs): # Iterate over a copy of dirs to allow modification
                    if d_name.lower().startswith("texture."):
                        full_path_str = str(root_path / d_name)
                        if full_path_str not in texture_dirs: # Ensure uniqueness
                            texture_dirs.append(full_path_str)
                        # Optional: dirs.remove(d_name) # To prevent descending into already found texture dirs
        except OSError as e:
            self.log(f"Error traversing directory {search_dir} for texture folders: {e}", "WARNING") # English
        
        if not texture_dirs:
             self.log(f"No 'texture.*' folders found in {directory}", "DETAIL") # English
        return texture_dirs

    def start_install_thread(self):
        errors = self.verify_settings()
        if errors:
            error_message = "Please correct the following configuration issues before installing:\n\n" + "\n".join(errors) # English
            messagebox.showerror("Configuration Errors", error_message) # English
            if any("Community" in e or "Reference" in e or "LocalState" in e or "Package" in e or PTP_CONVERTER_EXE_NAME in e for e in errors): # English keywords
                self.notebook.select(0) 
            elif any("Variant" in e or "livery" in e for e in errors): # English keywords
                self.notebook.select(1) 
            return

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Starting installation...") # English
        self.log("Starting installation process...", "STEP") # English
        self.install_button.config(state=tk.DISABLED)
        files_to_install = list(self.selected_zip_files) 
        install_thread = threading.Thread(target=self.install_livery_logic, args=(files_to_install,), daemon=True)
        install_thread.start()

    def _extract_archive(self, archive_path: Path, temp_dir: Path):
        self.log(f"Extracting ZIP archive '{archive_path.name}' to {temp_dir}...", "INFO") # English
        if archive_path.suffix.lower() != ".zip":
             raise ValueError(f"Unsupported file type for _extract_archive: {archive_path.name}. Only .zip.") # English
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                MAX_PATH_COMPONENT_LEN = 240 # A more conservative check for individual components
                for member_info in zip_ref.infolist():
                    member_path_str = member_info.filename
                    normalized_member_path = Path(member_path_str).as_posix()
                    if normalized_member_path.startswith('/') or '/../' in normalized_member_path or normalized_member_path.endswith('/..'):
                        raise ValueError(f"ZIP archive contains potentially unsafe path: {member_path_str}") # English
                    if len(member_path_str) > MAX_PATH_COMPONENT_LEN : 
                         self.log(f"Warning: Long path component in ZIP: '{member_path_str[:100]}...'", "WARNING") # English
                
                zip_ref.extractall(temp_dir)
            self.log(f"ZIP archive '{archive_path.name}' extracted successfully.", "SUCCESS") # English
        except zipfile.BadZipFile:
            raise ValueError(f"Invalid or corrupt ZIP archive: {archive_path.name}") # English
        except (OSError, OverflowError) as e_os: 
            if "path too long" in str(e_os).lower() or (hasattr(e_os, 'winerror') and e_os.winerror == 206): # ERROR_FILENAME_EXCED_RANGE
                 raise RuntimeError(f"Failed to extract '{archive_path.name}': File path too long within ZIP - {e_os}") # English
            raise RuntimeError(f"OS error extracting ZIP archive '{archive_path.name}': {e_os}") # English
        except Exception as e:
            raise RuntimeError(f"Failed to extract ZIP archive '{archive_path.name}': {e}") # English

    def _run_ptp_converter(self, ptp_file_path: Path, ptp_processing_base_dir: Path) -> tuple[bool, Path | None]:
        if not self.ptp_converter_exe or not os.path.exists(self.ptp_converter_exe):
            self.log(f"Error: {PTP_CONVERTER_EXE_NAME} not found. Cannot process {ptp_file_path.name}.", "ERROR") # English
            return False, None

        self.log(f"Processing PTP file '{ptp_file_path.name}' using {Path(self.ptp_converter_exe).name}...", "INFO") # English
        
        unique_ptp_output_folder_name = f"__ptp_extracted_{ptp_file_path.stem}_{datetime.now().strftime('%f')}"
        target_controlled_temp_dir = ptp_processing_base_dir / unique_ptp_output_folder_name
        
        original_ptp_file_parent_dir = ptp_file_path.parent
        converter_native_output_dir = original_ptp_file_parent_dir / ptp_file_path.stem
        
        try:
            target_controlled_temp_dir.mkdir(parents=True, exist_ok=True)
            
            if converter_native_output_dir.exists():
                self.log(f"Removing pre-existing PTP converter output folder: {converter_native_output_dir}", "DETAIL") # English
                try: shutil.rmtree(converter_native_output_dir)
                except Exception as e_rm:
                    self.log(f"Could not remove pre-existing PTP output folder '{converter_native_output_dir}': {e_rm}. Attempting to continue.", "WARNING") # English

            self.log(f"Executing: \"{self.ptp_converter_exe}\" \"{ptp_file_path}\" (CWD: {original_ptp_file_parent_dir})", "CMD") # English
            process = subprocess.run(
                [self.ptp_converter_exe, str(ptp_file_path)],
                capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore',
                cwd=str(original_ptp_file_parent_dir) 
            )

            if process.stdout: self.log(f"Output from {PTP_CONVERTER_EXE_NAME}:\n{process.stdout.strip()}", "DETAIL") # English
            if process.stderr: self.log(f"Errors from {PTP_CONVERTER_EXE_NAME}:\n{process.stderr.strip()}", "WARNING" if process.returncode == 0 and process.stderr else "ERROR") # English

            if process.returncode != 0:
                self.log(f"Execution of {PTP_CONVERTER_EXE_NAME} failed for '{ptp_file_path.name}'. Return code: {process.returncode}", "ERROR") # English
                return False, None

            if not converter_native_output_dir.is_dir():
                self.log(f"Expected extraction folder '{converter_native_output_dir}' was not created or is not a directory.", "ERROR") # English
                return False, None

            self.log(f"Moving extracted PTP content from '{converter_native_output_dir}' to '{target_controlled_temp_dir}'", "DETAIL") # English
            moved_count = 0
            for item_name in os.listdir(converter_native_output_dir):
                source_item = converter_native_output_dir / item_name
                destination_item = target_controlled_temp_dir / item_name
                try:
                    shutil.move(str(source_item), str(destination_item))
                    moved_count +=1
                except Exception as e_move:
                    self.log(f"Failed to move '{source_item.name}', attempting copy: {e_move}", "WARNING") # English
                    try:
                        if source_item.is_dir(): shutil.copytree(source_item, destination_item, dirs_exist_ok=True)
                        else: shutil.copy2(source_item, destination_item)
                        if source_item.is_dir(): shutil.rmtree(source_item)
                        else: source_item.unlink()
                        moved_count +=1
                    except Exception as e_copy_fb:
                         self.log(f"Fallback copy also failed for '{source_item.name}': {e_copy_fb}", "ERROR") # English
                         raise
            
            if moved_count > 0:
                 self.log(f"PTP content moved/copied. Removing original extraction container '{converter_native_output_dir}'.", "DETAIL") # English
                 try: shutil.rmtree(converter_native_output_dir) 
                 except Exception as e_rm_orig: self.log(f"Could not remove original PTP extraction folder '{converter_native_output_dir}': {e_rm_orig}", "WARNING") # English
            else:
                 self.log(f"Warning: No files were moved/copied from '{converter_native_output_dir}'. Was it empty?", "WARNING") # English

            self.log(f"PTP file '{ptp_file_path.name}' processed successfully. Content prepared in: {target_controlled_temp_dir}", "SUCCESS") # English
            return True, target_controlled_temp_dir
        except Exception as e:
            self.log(f"CRITICAL error during PTP processing for '{ptp_file_path.name}': {e}", "ERROR") # English
            import traceback
            self.log(f"PTP Traceback: {traceback.format_exc()}", "DETAIL") # English
            if target_controlled_temp_dir.exists(): # Clean up our controlled temp dir
                try: shutil.rmtree(target_controlled_temp_dir)
                except Exception as e_clean: self.log(f"Error cleaning up PTP temp folder '{target_controlled_temp_dir}' on failure: {e_clean}", "WARNING") # English
            if 'converter_native_output_dir' in locals() and converter_native_output_dir.exists():
                 try: shutil.rmtree(converter_native_output_dir)
                 except Exception as e_clean_native: self.log(f"Error cleaning converter's native output '{converter_native_output_dir}' on PTP failure: {e_clean_native}", "WARNING") # English
            return False, None

    def _reorganize_ptp_output(self, ptp_content_folder: Path) -> tuple[bool, str]:
        self.log(f"Reorganizing extracted PTP content in: {ptp_content_folder}", "STEP") # English
        try:
            config_cfg_original_path = ptp_content_folder / "Config.cfg"
            aircraft_cfg_final_path = ptp_content_folder / "aircraft.cfg"
            original_cfg_content_lines = []

            if config_cfg_original_path.is_file():
                self.log(f"Reading '{config_cfg_original_path.name}'...", "DETAIL") # English
                with open(config_cfg_original_path, 'r', encoding='utf-8', errors='ignore') as f: original_cfg_content_lines = f.readlines()
            elif aircraft_cfg_final_path.is_file():
                self.log(f"'{aircraft_cfg_final_path.name}' already exists. Processing its content.", "DETAIL") # English
                with open(aircraft_cfg_final_path, 'r', encoding='utf-8', errors='ignore') as f: original_cfg_content_lines = f.readlines()
            else:
                return False, f"Neither Config.cfg nor aircraft.cfg found in '{ptp_content_folder}'." # English

            if not original_cfg_content_lines: return False, "PTP configuration file is empty or could not be read." # English

            model_value_from_ptp_cfg = ""
            for line in original_cfg_content_lines:
                cleaned_line = line.strip().lower()
                if cleaned_line.startswith("model="):
                    model_value_from_ptp_cfg = line.split('=', 1)[1].strip().strip('"')
                    self.log(f"Detected original 'model={model_value_from_ptp_cfg}' in PTP config.", "DETAIL") # English
                    break 
            
            model_cfg_src_path = ptp_content_folder / "model.cfg"
            if model_cfg_src_path.is_file():
                target_model_folder_name = "model" 
                if model_value_from_ptp_cfg:
                    target_model_folder_name = f"model.{model_value_from_ptp_cfg}"
                model_folder_final_dest = ptp_content_folder / target_model_folder_name
                model_folder_final_dest.mkdir(exist_ok=True)
                target_model_cfg_final_path = model_folder_final_dest / "model.cfg"
                self.log(f"Moving '{model_cfg_src_path.name}' to '{target_model_cfg_final_path}'", "DETAIL") # English
                shutil.move(str(model_cfg_src_path), str(target_model_cfg_final_path))
            else: self.log("model.cfg not found in PTP output. Skipping model folder creation.", "DETAIL") # English

            processed_lines_for_aircraft_cfg = []
            fltsim_header_normalized = False
            for line_content in original_cfg_content_lines:
                if not fltsim_header_normalized and line_content.strip().lower().startswith("[fltsim."):
                    normalized_header = re.sub(r'\[fltsim\.[^\]]*\]', '[fltsim.0]', line_content.strip(), count=1, flags=re.IGNORECASE)
                    line_ending = '\r\n' if line_content.endswith('\r\n') else '\n'
                    processed_lines_for_aircraft_cfg.append(normalized_header + line_ending)
                    if line_content.strip().lower() != normalized_header.lower():
                        self.log(f"Normalized header '{line_content.strip()}' to '{normalized_header}'.", "DETAIL") # English
                    fltsim_header_normalized = True
                else:
                    processed_lines_for_aircraft_cfg.append(line_content)
            
            final_cfg_body_str = "".join(processed_lines_for_aircraft_cfg)
            if not fltsim_header_normalized:
                 self.log("WARNING: No [fltsim.x] type section found/normalized in PTP config file.", "WARNING") # English

            if not final_cfg_body_str.lstrip().lower().startswith("[version]"):
                final_cfg_content_to_write = "[VERSION]\nmajor=1\nminor=0\n\n" + final_cfg_body_str
                self.log("[VERSION] section prepended to aircraft.cfg content.", "DETAIL") # English
            else:
                final_cfg_content_to_write = final_cfg_body_str
                self.log("aircraft.cfg content already started with [VERSION].", "DETAIL") # English
            
            with open(aircraft_cfg_final_path, 'w', encoding='utf-8', newline='') as f_write:
                f_write.write(final_cfg_content_to_write)
            self.log(f"'{aircraft_cfg_final_path.name}' saved. (Original 'model=' line preserved: 'model={model_value_from_ptp_cfg}')", "SUCCESS") # English
            
            if config_cfg_original_path.is_file() and config_cfg_original_path.resolve() != aircraft_cfg_final_path.resolve():
                try: config_cfg_original_path.unlink(); self.log(f"Original '{config_cfg_original_path.name}' deleted.", "DETAIL") # English
                except OSError as e: self.log(f"Warning: Could not delete original '{config_cfg_original_path.name}': {e}", "WARNING") # English

            (ptp_content_folder / "Settings.dat").unlink(missing_ok=True)
            self.log("Attempted deletion of 'Settings.dat' (if it existed).", "DETAIL") # English
            
            aircraft_ini = ptp_content_folder / "Aircraft.ini"
            options_ini = ptp_content_folder / "options.ini"
            if aircraft_ini.is_file():
                aircraft_ini.rename(options_ini)
                self.log(f"Renamed '{aircraft_ini.name}' to '{options_ini.name}'.", "DETAIL") # English
            elif options_ini.is_file(): self.log("'options.ini' already exists.", "DETAIL") # English
            else: self.log("Neither 'Aircraft.ini' nor 'options.ini' found in PTP output.", "DETAIL") # English

            self.log("PTP content reorganization (dynamic model folder naming) completed successfully.", "SUCCESS") # English
            return True, ""
        except Exception as e:
            self.log(f"CRITICAL error during PTP reorganization in '{ptp_content_folder}': {e}", "ERROR") # English
            import traceback
            self.log(f"PTP Reorganization Traceback: {traceback.format_exc()}", "DETAIL") # English
            return False, f"Critical error in PTP reorganization: {e}" # English

    def _is_nested_archive(self, directory: Path) -> bool:
        zip_count = 0
        ptp_count = 0 # Added for PTP detection
        other_file_folder_count = 0
        has_texture_folder = False
        check_dir = directory
        try:
            items = list(check_dir.iterdir())
            if len(items) == 1 and items[0].is_dir() and not items[0].name.startswith(('.', '__MACOSX')):
                check_dir = items[0]
            
            for item in check_dir.iterdir():
                if item.name.startswith(('.', '__MACOSX')): continue
                if item.is_file():
                    if item.suffix.lower() == '.zip': zip_count += 1
                    elif item.suffix.lower() == '.ptp': ptp_count += 1 # Count PTPs
                    else: other_file_folder_count += 1
                elif item.is_dir():
                    other_file_folder_count += 1
                    if item.name.lower().startswith('texture.'): has_texture_folder = True
        except OSError as e:
            self.log(f"Error checking directory for nested archives in '{check_dir}': {e}", "WARNING") # English
            return False
        
        archive_file_count = zip_count + ptp_count
        is_nested = (archive_file_count > 0 and not has_texture_folder) or \
                    (archive_file_count > 0 and other_file_folder_count <= 2)
        
        if is_nested:
            self.log(f"Nested archive structure detected in '{check_dir.name}'. ZIPs: {zip_count}, PTPs: {ptp_count}, Others: {other_file_folder_count}, HasTexture: {has_texture_folder}.", "INFO") # English
        return is_nested

    def _process_single_livery(self,
                               extracted_livery_source_path: Path,
                               original_archive_path: Path,
                               common_config: dict
                               ) -> tuple[bool, str]:
        """
        Processes a single prepared livery from 'extracted_livery_source_path'.
        Copies files to the final destination, modifies aircraft.cfg, handles .ini.
        Attempts to clean up its own created destination folder on failure.
        """
        livery_success = False
        processing_error_detail = "Unknown error during individual livery processing." # English
        livery_display_name = "Unknown Livery" # English
        final_livery_dest_path: Path | None = None

        try:
            livery_display_name = self.get_livery_name(original_archive_path, extracted_livery_source_path)
            sanitized_fs_foldername = re.sub(r'[\\/*?:"<>|]', '_', livery_display_name).strip()
            if not sanitized_fs_foldername:
                sanitized_fs_foldername = f"Unnamed_{original_archive_path.stem}"
                self.log(f"Sanitized livery name was empty, using '{sanitized_fs_foldername}'.", "WARNING") # English

            final_livery_dest_path = common_config['main_package_folder'] / "SimObjects" / "Airplanes" / \
                                     f"{common_config['base_aircraft_folder_name']} {sanitized_fs_foldername}"
            self.log(f"Final livery destination folder: {final_livery_dest_path}", "DETAIL") # English

            if final_livery_dest_path.exists():
                self.log(f"Destination folder already exists. Overwriting: {final_livery_dest_path}", "WARNING") # English
                try:
                    shutil.rmtree(final_livery_dest_path)
                    self.log(f"Existing destination folder deleted.", "DETAIL") # English
                    time.sleep(0.1)
                except OSError as e:
                    if sys.platform == "win32" and isinstance(e, PermissionError):
                        raise RuntimeError(f"Failed to delete existing folder '{final_livery_dest_path}'. Is MSFS or File Explorer using it?") # English
                    else:
                        raise RuntimeError(f"Failed to delete existing livery folder '{final_livery_dest_path}': {e}.") # English
            
            final_livery_dest_path.mkdir(parents=True, exist_ok=True)
            self.log("Final livery destination folder created/cleaned.", "SUCCESS") # English

            self.log(f"Copying files from processed source: {extracted_livery_source_path}", "INFO") # English

            aircraft_cfg_source_str = self.find_file_in_dir(extracted_livery_source_path, "aircraft.cfg")
            if not aircraft_cfg_source_str:
                raise FileNotFoundError(f"aircraft.cfg not found in processed source folder '{extracted_livery_source_path}'.") # English
            aircraft_cfg_source_path = Path(aircraft_cfg_source_str)
            aircraft_cfg_final_target_path = final_livery_dest_path / "aircraft.cfg"
            shutil.copy2(aircraft_cfg_source_path, aircraft_cfg_final_target_path)
            self.log(f"Copied '{aircraft_cfg_source_path.name}' to '{aircraft_cfg_final_target_path}'.", "DETAIL") # English
            
            model_folder_copied = False
            for item in extracted_livery_source_path.iterdir():
                if item.is_dir() and item.name.lower().startswith("model"):
                    model_src_path = item
                    model_dest_path = final_livery_dest_path / model_src_path.name
                    self.log(f"Copying model folder '{model_src_path.name}' to '{model_dest_path}'...", "DETAIL") # English
                    shutil.copytree(model_src_path, model_dest_path, dirs_exist_ok=True)
                    model_folder_copied = True
                    break 
            if not model_folder_copied:
                self.log("Model folder (or 'model.XXX') not found in source. This may be normal.", "DETAIL") # English

            texture_dirs_source_str_list = self.find_texture_dirs_in_dir(extracted_livery_source_path)
            if not texture_dirs_source_str_list:
                raise FileNotFoundError(f"'texture.*' folders not found in processed source folder '{extracted_livery_source_path}'.") # English
            for tex_dir_src_str in texture_dirs_source_str_list:
                tex_dir_src_path = Path(tex_dir_src_str)
                tex_dir_dest_path = final_livery_dest_path / tex_dir_src_path.name
                shutil.copytree(tex_dir_src_path, tex_dir_dest_path, dirs_exist_ok=True)
                self.log(f"Copied texture folder '{tex_dir_src_path.name}' to '{tex_dir_dest_path}'.", "DETAIL") # English
            
            copied_extras_count = 0
            source_config_parent_dir = aircraft_cfg_source_path.parent 
            atc_id_for_exclusion = self.extract_atc_id(aircraft_cfg_final_target_path)
            files_to_exclude_lc = {"aircraft.cfg", "options.ini", "layout.json", "manifest.json", 
                                   "config.cfg", "aircraft.ini", "settings.dat", "model.cfg"}
            if atc_id_for_exclusion:
                files_to_exclude_lc.add(f"{atc_id_for_exclusion}.ini".lower())

            for item_name in os.listdir(source_config_parent_dir):
                item_src_full_path = source_config_parent_dir / item_name
                if item_src_full_path.is_dir() and (item_name.lower().startswith("model") or item_name.lower().startswith("texture.")):
                    continue 
                if item_src_full_path.is_file() and item_name.lower() in files_to_exclude_lc:
                    continue 
                if item_src_full_path.is_file():
                    if item_src_full_path.suffix.lower() in ['.json', '.ini', '.cfg', '.xml', '.dat', '.txt', '.flags', '.ttf', '.otf']:
                        item_dest_full_path = final_livery_dest_path / item_name
                        try:
                            shutil.copy2(item_src_full_path, item_dest_full_path)
                            copied_extras_count += 1
                        except Exception as e_copy_ex:
                            self.log(f"Could not copy extra file '{item_name}': {e_copy_ex}", "WARNING") # English
            if copied_extras_count > 0: self.log(f"Copied {copied_extras_count} additional extra files.", "DETAIL") # English
            self.log("Essential livery file copying complete.", "SUCCESS") # English

            self.log("Processing options.ini...", "INFO") # English
            atc_id_from_final_cfg = self.extract_atc_id(aircraft_cfg_final_target_path)
            options_ini_in_source_str = self.find_file_in_dir(extracted_livery_source_path, "options.ini")
            source_ini_to_copy_path: Path | None = None
            target_ini_name_in_localstate: str | None = None
            ini_file_found_in_source = False
            ini_copied_to_localstate = False

            if atc_id_from_final_cfg:
                target_ini_name_in_localstate = f"{atc_id_from_final_cfg}.ini"
                if options_ini_in_source_str and Path(options_ini_in_source_str).is_file():
                    source_ini_to_copy_path = Path(options_ini_in_source_str)
                    ini_file_found_in_source = True
                    self.log(f"Found '{source_ini_to_copy_path.name}' in processed source.", "DETAIL") # English
                else: 
                    atc_id_ini_in_source_str = self.find_file_in_dir(extracted_livery_source_path, target_ini_name_in_localstate.lower())
                    if atc_id_ini_in_source_str and Path(atc_id_ini_in_source_str).is_file():
                        source_ini_to_copy_path = Path(atc_id_ini_in_source_str)
                        ini_file_found_in_source = True
                        self.log(f"Found '{source_ini_to_copy_path.name}' (pre-named) in processed source.", "DETAIL") # English
            
            if ini_file_found_in_source and source_ini_to_copy_path and target_ini_name_in_localstate:
                pmdg_ls_pkg_path = common_config['pmdg_localstate_package_path']
                if pmdg_ls_pkg_path.is_dir():
                    target_ini_storage_dir = pmdg_ls_pkg_path / "work" / "Aircraft"
                    target_ini_final_path = target_ini_storage_dir / target_ini_name_in_localstate
                    try:
                        target_ini_storage_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_ini_to_copy_path, target_ini_final_path)
                        self.log(f"INI file '{source_ini_to_copy_path.name}' copied as '{target_ini_name_in_localstate}' to: {target_ini_storage_dir}", "SUCCESS") # English
                        ini_copied_to_localstate = True
                    except Exception as e_cp_ini:
                        self.log(f"Failed to copy INI file '{source_ini_to_copy_path.name}' to '{target_ini_final_path}': {e_cp_ini}", "ERROR") # English
                else:
                    self.log(f"PMDG LocalState Package Path for {common_config['aircraft_variant']} is invalid: {pmdg_ls_pkg_path}. Cannot copy INI file.", "ERROR") # English
            elif atc_id_from_final_cfg: 
                self.log(f"Neither 'options.ini' nor '{atc_id_from_final_cfg}.ini' found in processed source folder to copy to LocalState.", "DETAIL") # English
            else: 
                self.log("Valid ATC ID not found in aircraft.cfg; cannot process .ini file for LocalState.", "WARNING") # English

            self.log(f"Modifying aircraft.cfg in final destination: {aircraft_cfg_final_target_path}...", "INFO") # English
            self.modify_aircraft_cfg(aircraft_cfg_final_target_path, common_config['aircraft_variant'], livery_display_name)

            livery_success = True
            processing_error_detail = "Installed successfully." # English
            if ini_file_found_in_source and not ini_copied_to_localstate and atc_id_from_final_cfg:
                ini_name_msg = source_ini_to_copy_path.name if source_ini_to_copy_path else "INI file" # English
                processing_error_detail += f" (Warning: {ini_name_msg} found but failed to copy to LocalState)" # English

        except (FileNotFoundError, ValueError, RuntimeError, OSError) as e_proc:
            processing_error_detail = str(e_proc)
            self.log(f"LIVERY PROCESSING FAILED ({livery_display_name} from {original_archive_path.name}): {processing_error_detail}", "ERROR") # English
        except Exception as e_unexp: 
            processing_error_detail = f"Unexpected error processing livery {livery_display_name} (from {original_archive_path.name}): {str(e_unexp)}" # English
            self.log(f"FATAL LIVERY ERROR ({livery_display_name}): {processing_error_detail}", "ERROR") # English
            import traceback 
            self.log(f"Traceback _process_single_livery: {traceback.format_exc()}", "DETAIL")
        
        if not livery_success and final_livery_dest_path and final_livery_dest_path.exists():
            self.log(f"Failure in _process_single_livery for '{livery_display_name}'. Attempting to remove created destination folder: {final_livery_dest_path}", "WARNING") # English
            try:
                shutil.rmtree(final_livery_dest_path)
                self.log(f"Destination folder of failed livery removed: {final_livery_dest_path}", "INFO") # English
            except Exception as e_cleanup:
                self.log(f"Error attempting to remove destination folder of failed livery '{final_livery_dest_path}': {e_cleanup}", "ERROR") # English
        
        return livery_success, processing_error_detail

    def install_livery_logic(self, archive_paths_to_process: list[str]):
        num_files_initial = len(archive_paths_to_process)
        total_archives_processed = 0
        successful_liveries_installed = 0
        failed_liveries_or_archives = 0
        results_summary: list[dict] = []

        try:
            community_path = Path(self.community_path_var.get())
            reference_livery_path = Path(self.reference_path_var.get())
            pmdg_variant_paths = {
                "200ER": Path(self.pmdg_77er_path_var.get()),
                "300ER": Path(self.pmdg_77w_path_var.get()),
                "F": Path(self.pmdg_77f_path_var.get())
            }
            current_aircraft_variant = self.aircraft_variant_var.get()
            pmdg_localstate_for_variant = pmdg_variant_paths.get(current_aircraft_variant)

            if not pmdg_localstate_for_variant or not pmdg_localstate_for_variant.is_dir():
                raise ValueError(f"PMDG Package Path (LocalState) for variant '{current_aircraft_variant}' is invalid or not set.") # English

            target_package_name = VARIANT_PACKAGE_MAP.get(current_aircraft_variant)
            if not target_package_name: raise ValueError(f"Package mapping not found for variant: {current_aircraft_variant}") # English
            target_package_root_path = community_path / target_package_name
            
            base_simobject_pmdg_folder_name = VARIANT_BASE_AIRCRAFT_MAP.get(current_aircraft_variant)
            if not base_simobject_pmdg_folder_name: raise ValueError(f"PMDG base folder name not found for variant: {current_aircraft_variant}") # English

            common_install_config = {
                'reference_livery_path': reference_livery_path,
                'pmdg_localstate_package_path': pmdg_localstate_for_variant,
                'aircraft_variant': current_aircraft_variant,
                'main_package_folder': target_package_root_path,
                'base_aircraft_folder_name': base_simobject_pmdg_folder_name,
            }

            target_package_root_path.mkdir(parents=True, exist_ok=True)
            manifest_path_in_package = target_package_root_path / "manifest.json"
            layout_path_in_package = target_package_root_path / "layout.json"

            if not manifest_path_in_package.exists():
                ref_manifest_path = reference_livery_path / "manifest.json"
                if not ref_manifest_path.is_file():
                    raise FileNotFoundError(f"Reference manifest.json not found at '{reference_livery_path}' and no destination manifest exists.") # English
                self.log(f"Copying manifest.json from reference to '{manifest_path_in_package}'", "INFO") # English
                shutil.copy2(ref_manifest_path, manifest_path_in_package)
            
            try:
                dep_name = VARIANT_DEPENDENCY_MAP.get(current_aircraft_variant)
                dep_list = [{"name": dep_name}] if dep_name else []
                if not dep_name: self.log(f"Could not determine dependency for variant '{current_aircraft_variant}'.", "ERROR") # English
                else: self.log(f"Ensuring dependency '{dep_name}' in '{manifest_path_in_package.name}'.", "INFO") # English

                m_data = {}
                if manifest_path_in_package.is_file():
                    with open(manifest_path_in_package, 'r', encoding='utf-8') as f: m_data = json.load(f)
                
                m_data.update({
                    "dependencies": dep_list, "content_type": "LIVERY",
                    "title": f"Livery Pack: PMDG {current_aircraft_variant}", "manufacturer": m_data.get("manufacturer", "PMDG"),
                    "creator": f"Community / {self.app_version}", "package_version": m_data.get("package_version", "1.0.0"),
                    "minimum_game_version": DEFAULT_MIN_GAME_VERSION,
                    "total_package_size": m_data.get("total_package_size", "0"*20),
                })
                if "release_notes" not in m_data: m_data["release_notes"] = {"neutral": {"LastUpdate": "", "OlderHistory": ""}}
                with open(manifest_path_in_package, 'w', encoding='utf-8', newline='\n') as f: json.dump(m_data, f, indent=4)
                self.log("Manifest.json (dependency and metadata) verified/updated.", "SUCCESS") # English
            except Exception as e_mf_init:
                self.log(f"ERROR updating initial manifest.json metadata: {e_mf_init}", "ERROR") # English

            if not layout_path_in_package.exists():
                ref_layout_path = reference_livery_path / "layout.json"
                if ref_layout_path.is_file():
                    self.log(f"Copying layout.json template from reference to '{layout_path_in_package}'", "INFO") # English
                    shutil.copy2(ref_layout_path, layout_path_in_package)
        
        except Exception as config_err:
            self.log(f"CRITICAL ERROR during initial installation setup: {config_err}", "ERROR") # English
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "DETAIL")
            self.master.after(0, lambda: self.status_var.set("Installation failed! (Configuration Error)")) # English
            self.master.after(0, lambda: self.install_button.config(state=tk.NORMAL))
            messagebox.showerror("Critical Error", f"Could not configure installation:\n{config_err}") # English
            return

        for idx, archive_file_path_str in enumerate(archive_paths_to_process):
            original_archive_path = Path(archive_file_path_str)
            log_archive_name = original_archive_path.name
            self.log(f"--- Starting processing for: {log_archive_name} ({idx + 1}/{num_files_initial}) ---", "STEP") # English
            self.master.after(0, lambda i=idx, n=log_archive_name: self.status_var.set(f"Processing {i + 1}/{num_files_initial}: {n}...")) # English

            top_level_temp_dirs_for_this_archive: list[Path] = []
            archive_had_at_least_one_success_sub_livery = False 
            archive_had_at_least_one_failure_sub_livery = False

            try:
                if original_archive_path.suffix.lower() == ".ptp":
                    ptp_processing_temp_base = target_package_root_path / f"__temp_ptp_proc_{original_archive_path.stem}_{datetime.now().strftime('%f')}"
                    ptp_processing_temp_base.mkdir(parents=True, exist_ok=True)
                    top_level_temp_dirs_for_this_archive.append(ptp_processing_temp_base)

                    conversion_ok, ptp_reorganized_folder = self._run_ptp_converter(original_archive_path, ptp_processing_temp_base)
                    if not conversion_ok or not ptp_reorganized_folder:
                        raise RuntimeError(f"PTP conversion failed for {log_archive_name}.") # English
                    
                    reorg_ok, reorg_msg = self._reorganize_ptp_output(ptp_reorganized_folder)
                    if not reorg_ok:
                        raise RuntimeError(f"PTP reorganization failed for {log_archive_name}: {reorg_msg}") # English
                    
                    livery_ok, detail = self._process_single_livery(ptp_reorganized_folder, original_archive_path, common_install_config)
                    results_summary.append({"file": log_archive_name, "success": livery_ok, "detail": detail})
                    if livery_ok: archive_had_at_least_one_success_sub_livery = True
                    else: archive_had_at_least_one_failure_sub_livery = True
                
                elif original_archive_path.suffix.lower() == ".zip":
                    zip_extract_base_temp_dir = target_package_root_path / f"__temp_zip_extract_{log_archive_name}_{datetime.now().strftime('%f')}"
                    zip_extract_base_temp_dir.mkdir(parents=True, exist_ok=True)
                    top_level_temp_dirs_for_this_archive.append(zip_extract_base_temp_dir)
                    self._extract_archive(original_archive_path, zip_extract_base_temp_dir)

                    items_in_zip_extract = list(zip_extract_base_temp_dir.iterdir())
                    effective_content_dir_for_zip = zip_extract_base_temp_dir
                    if len(items_in_zip_extract) == 1 and items_in_zip_extract[0].is_dir() and \
                       not items_in_zip_extract[0].name.startswith(('.', '__MACOSX')):
                        effective_content_dir_for_zip = items_in_zip_extract[0]

                    if self._is_nested_archive(effective_content_dir_for_zip):
                        nested_archives = list(effective_content_dir_for_zip.glob('*.zip')) + \
                                          list(effective_content_dir_for_zip.glob('*.ptp'))
                        if not nested_archives:
                            self.log(f"'{log_archive_name}' detected as nested but no .zip or .ptp files found inside. Attempting to process as single livery.", "WARNING") # English
                            livery_ok, detail = self._process_single_livery(effective_content_dir_for_zip, original_archive_path, common_install_config)
                            results_summary.append({"file": log_archive_name, "success": livery_ok, "detail": detail})
                            if livery_ok: archive_had_at_least_one_success_sub_livery = True
                            else: archive_had_at_least_one_failure_sub_livery = True
                        else:
                            self.log(f"'{log_archive_name}' contains {len(nested_archives)} nested archive(s). Processing individually...", "INFO") # English
                            all_nested_current_pack_ok = True
                            for nested_idx, nested_path in enumerate(nested_archives):
                                nested_log_name = nested_path.name
                                self.log(f"--- Processing nested {nested_idx + 1}/{len(nested_archives)}: {nested_log_name} (from {log_archive_name}) ---", "STEP") # English
                                
                                nested_processing_base = zip_extract_base_temp_dir / f"__nested_proc_{nested_path.stem}_{datetime.now().strftime('%f')}"
                                nested_source_folder: Path | None = None # Renamed for clarity
                                try:
                                    nested_processing_base.mkdir(parents=True, exist_ok=True)
                                    if nested_path.suffix.lower() == ".ptp":
                                        conv_ok, conv_folder = self._run_ptp_converter(nested_path, nested_processing_base)
                                        if not conv_ok or not conv_folder: raise RuntimeError(f"Nested PTP conversion failed: {nested_log_name}") # English
                                        re_ok, re_detail = self._reorganize_ptp_output(conv_folder)
                                        if not re_ok: raise RuntimeError(f"Nested PTP reorganization failed for '{nested_log_name}': {re_detail}") # English
                                        nested_source_folder = conv_folder
                                    elif nested_path.suffix.lower() == ".zip":
                                        nested_zip_extract_target = nested_processing_base / f"__extracted_nested_zip_{nested_path.stem}"
                                        nested_zip_extract_target.mkdir(exist_ok=True)
                                        self._extract_archive(nested_path, nested_zip_extract_target)
                                        
                                        items_in_n_extract = list(nested_zip_extract_target.iterdir())
                                        nested_source_folder = nested_zip_extract_target
                                        if len(items_in_n_extract) == 1 and items_in_n_extract[0].is_dir() and not items_in_n_extract[0].name.startswith(('.', '__MACOSX')):
                                            nested_source_folder = items_in_n_extract[0]
                                    else: 
                                        self.log(f"Unsupported nested file type: {nested_log_name}", "WARNING"); continue # English

                                    if nested_source_folder:
                                        liv_ok, det = self._process_single_livery(nested_source_folder, nested_path, common_install_config)
                                        results_summary.append({"file": f"{log_archive_name} -> {nested_log_name}", "success": liv_ok, "detail": det})
                                        if not liv_ok: all_nested_current_pack_ok = False
                                        else: archive_had_at_least_one_success_sub_livery = True # Mark that parent had some success
                                    else:
                                        results_summary.append({"file": f"{log_archive_name} -> {nested_log_name}", "success": False, "detail": "Could not determine nested source folder."}) # English
                                        all_nested_current_pack_ok = False
                                except Exception as e_nest_proc:
                                    results_summary.append({"file": f"{log_archive_name} -> {nested_log_name}", "success": False, "detail": str(e_nest_proc)})
                                    all_nested_current_pack_ok = False
                                finally:
                                    if nested_processing_base.exists(): shutil.rmtree(nested_processing_base)
                            
                            if not all_nested_current_pack_ok : archive_had_at_least_one_failure_sub_livery = True

                    else: # Not a nested ZIP
                        self.log(f"Processing '{log_archive_name}' as a single ZIP livery.", "INFO") # English
                        livery_ok, detail = self._process_single_livery(effective_content_dir_for_zip, original_archive_path, common_install_config)
                        results_summary.append({"file": log_archive_name, "success": livery_ok, "detail": detail})
                        if livery_ok: archive_had_at_least_one_success_sub_livery = True
                        else: archive_had_at_least_one_failure_sub_livery = True
                else:
                    raise ValueError(f"Unrecognized file type: {log_archive_name}") # English
                
                # Update overall batch success/fail counts based on this main archive's outcome
                if archive_had_at_least_one_failure_sub_livery: # If any part of this archive (or its children) failed
                    failed_liveries_or_archives += 1
                elif archive_had_at_least_one_success_sub_livery: # If all parts of this archive (and its children) were successful
                    successful_liveries_installed += 1
                # If archive_had_at_least_one_success_sub_livery is False AND archive_had_at_least_one_failure_sub_livery is False
                # it means it was an empty pack or something unprocessable that didn't explicitly error but also didn't yield success.
                # In this case, we can count it as a failure for the main archive.
                elif not archive_had_at_least_one_success_sub_livery and not archive_had_at_least_one_failure_sub_livery:
                     if original_archive_path.suffix.lower() == ".zip" and self._is_nested_archive(effective_content_dir_for_zip):
                        self.log(f"Archive '{log_archive_name}' considered failed as it was a pack with no successful liveries.", "WARNING")
                        failed_liveries_or_archives +=1

                total_archives_processed += 1
            
            except Exception as e_outer_loop_proc:
                self.log(f"CRITICAL error processing input file '{log_archive_name}': {e_outer_loop_proc}", "ERROR") # English
                import traceback
                self.log(f"Input file processing traceback: {traceback.format_exc()}", "DETAIL") # English
                results_summary.append({"file": log_archive_name, "success": False, "detail": str(e_outer_loop_proc)})
                failed_liveries_or_archives += 1
                total_archives_processed += 1
            finally:
                for temp_dir in top_level_temp_dirs_for_this_archive:
                    if temp_dir.exists():
                        try:
                            shutil.rmtree(temp_dir)
                            self.log(f"Main processing temp folder '{temp_dir.name}' deleted.", "DETAIL") # English
                        except Exception as e_clean_main:
                            self.log(f"Could not delete main processing temp folder '{temp_dir.name}': {e_clean_main}", "WARNING") # English
            
            progress_update = ((idx + 1) / num_files_initial) * 85
            self.master.after(0, lambda p=progress_update: self.progress_var.set(min(p, 85.0)))
        
        # (Continuation of install_livery_logic, after the main processing loop)

        # --- Step 7: Automatic Layout Generation & Manifest Update for the Package ---
        layout_gen_success = False
        layout_gen_error_detail = ""
        manifest_update_success = False # For the final total_package_size update
        manifest_error_detail = ""

        # Only proceed if ALL archives processed in the current batch were successful
        if failed_liveries_or_archives == 0 and successful_liveries_installed > 0:
            self.log(f"--- All {successful_liveries_installed} liveries processed successfully in this batch. " # English
                     f"Starting layout.json generation / manifest.json update for package: {target_package_root_path.name} ---", "STEP") # English
            self.master.after(0, lambda: self.status_var.set("Generating layout.json...")) # English

            try:
                layout_success_bool, layout_err_str, content_total_size, layout_file_size = \
                    self._generate_layout_file(target_package_root_path)
            except Exception as e_gen_layout:
                layout_success_bool = False
                layout_err_str = f"Critical exception in _generate_layout_file: {e_gen_layout}" # English
                self.log(layout_err_str, "ERROR")
                import traceback
                self.log(f"Traceback _generate_layout_file: {traceback.format_exc()}", "DETAIL")

            if layout_success_bool:
                layout_gen_success = True
                self.master.after(0, lambda: self.progress_var.set(95))
                self.master.after(0, lambda: self.status_var.set("Updating manifest.json...")) # English

                manifest_path_in_pkg = target_package_root_path / "manifest.json"
                current_manifest_actual_size = 0
                if manifest_path_in_pkg.is_file():
                    try: current_manifest_actual_size = manifest_path_in_pkg.stat().st_size
                    except Exception as e_stat: self.log(f"Warning: Could not get size of existing manifest.json: {e_stat}", "WARNING") # English
                
                final_total_package_size_val = content_total_size + layout_file_size + current_manifest_actual_size
                
                try:
                    manifest_size_update_ok = self._update_manifest_file(manifest_path_in_pkg, final_total_package_size_val)
                except Exception as e_upd_manifest:
                    manifest_size_update_ok = False
                    manifest_error_detail = f"Critical exception in _update_manifest_file: {e_upd_manifest}" # English
                    self.log(manifest_error_detail, "ERROR")
                    import traceback
                    self.log(f"Traceback _update_manifest_file: {traceback.format_exc()}", "DETAIL")

                if manifest_size_update_ok:
                    manifest_update_success = True
                    self.master.after(0, lambda: self.progress_var.set(100))
                else:
                    if not manifest_error_detail:
                        manifest_error_detail = "Failed to update total_package_size in manifest.json. See log." # English
                    self.log(manifest_error_detail, "ERROR")
            else:
                layout_gen_error_detail = f"Failed to generate layout.json: {layout_err_str}. See log." # English
                self.log(layout_gen_error_detail, "ERROR")
                self.master.after(0, lambda: self.progress_var.set(min(self.progress_var.get(), 90)))
        
        elif successful_liveries_installed > 0 and failed_liveries_or_archives > 0:
            self.log(f"{successful_liveries_installed} liveries processed successfully, but {failed_liveries_or_archives} archive(s)/livery(s) failed. " # English
                     f"SKIPPING layout.json and manifest.json update for package '{target_package_root_path.name}' to maintain consistency.", "WARNING") # English
        elif total_archives_processed > 0 and successful_liveries_installed == 0 :
            self.log(f"All {total_archives_processed} attempted livery installations failed. " # English
                     f"layout.json and manifest.json for package '{target_package_root_path.name}' will not be updated.", "ERROR") # English
        else: # No archives were processed (total_archives_processed == 0)
             self.log(f"No archives processed. No update required for layout.json or manifest.json for package '{target_package_root_path.name}'.", "INFO") # English

        # --- Final Notification ---
        post_processing_attempted_this_run = (failed_liveries_or_archives == 0 and successful_liveries_installed > 0)
        final_layout_manifest_update_success = layout_gen_success and manifest_update_success if post_processing_attempted_this_run else False
        
        final_post_proc_error_msg = ""
        if post_processing_attempted_this_run:
            if not final_layout_manifest_update_success:
                final_post_proc_error_msg = layout_gen_error_detail or manifest_error_detail
        elif failed_liveries_or_archives > 0 :
             final_post_proc_error_msg = "Layout/Manifest update SKIPPED due to failures in one or more individual liveries." # English
        
        if total_archives_processed == 0: final_batch_status_message = "No files processed." # English
        elif failed_liveries_or_archives == 0 and final_layout_manifest_update_success : final_batch_status_message = "Completed" # English
        elif successful_liveries_installed > 0: final_batch_status_message = "Completed with errors" # English
        else: final_batch_status_message = "Failed" # English
            
        self.master.after(0, lambda msg=final_batch_status_message: self.status_var.set(msg))
        
        def finalize_ui_and_reset():
            self.install_button.config(state=tk.NORMAL)
            self._reset_install_fields()
            self.log("Batch installation process finished. Ready for new operation.", "STEP") # English

        self.master.after(100, lambda: self.show_multi_final_message(
            results_summary, 
            final_layout_manifest_update_success,
            final_post_proc_error_msg, 
            str(target_package_root_path) # Ensure it's a string for the message
            )
        )
        self.master.after(300, finalize_ui_and_reset)

    def _reset_install_fields(self):
        self.log("Resetting install tab fields.", "DETAIL") # English
        self.selected_zip_files = []
        self.livery_zip_display_var.set("")
        self.custom_name_var.set("")
        if hasattr(self, 'custom_name_entry') and self.custom_name_entry: # Check widget exists
            self.custom_name_entry.config(state=tk.NORMAL)
        # self.status_var.set("Ready") # Already handled by finalize_ui_and_reset or similar

    def modify_aircraft_cfg(self, cfg_path: Path, aircraft_variant: str, livery_title: str): # livery_title not used currently
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Cannot modify aircraft.cfg, file not found: {cfg_path}") # English

        correct_base_folder_name = VARIANT_BASE_AIRCRAFT_MAP.get(aircraft_variant)
        if not correct_base_folder_name:
            raise ValueError(f"Invalid variant '{aircraft_variant}' for aircraft.cfg.") # English

        try:
            with open(cfg_path, 'r', encoding='utf-8', errors='ignore', newline='') as f: lines = f.readlines()
        except Exception as e: raise RuntimeError(f"Error reading aircraft.cfg file '{cfg_path}': {e}") # English

        target_variation_base_container_value = f'"..\\{correct_base_folder_name}"'
        if aircraft_variant == "200ER":
            self.log("Processing 777-200ER: Checking for engine suffix in original [VARIATION]...", "DETAIL") # English
            in_variation_s_read = False; original_bc_line = None
            for line_r in lines:
                s_line_r = line_r.strip()
                if s_line_r.lower() == '[variation]': in_variation_s_read = True; continue
                if in_variation_s_read:
                    if s_line_r.startswith('['): break 
                    if re.match(r'^\s*base_container\s*=', s_line_r,re.IGNORECASE): original_bc_line = s_line_r; break
            if original_bc_line:
                bc_match = re.match(r'^\s*base_container\s*=\s*"?(.+?)"?\s*$',original_bc_line,re.IGNORECASE)
                if bc_match:
                    existing_val = bc_match.group(1).strip().replace('/','\\')
                    engine_match = re.search(rf'{re.escape(correct_base_folder_name)}\s+(GE|RR|PW)\b',existing_val,re.IGNORECASE)
                    if eng_match:
                        target_variation_base_container_value = f'"..\\{correct_base_folder_name} {eng_match.group(1).upper()}"'
                        self.log(f"Preserved engine suffix '{eng_match.group(1).upper()}' for base_container.", "INFO") # English
        
        target_bc_line_content = f'base_container = {target_variation_base_container_value}'
        self.log(f"Target [VARIATION] base_container line: {target_bc_line_content}", "DETAIL") # English
        
        output_lines = []
        needs_rewrite = False
        variation_section_found_cfg = any(line.strip().lower() == '[variation]' for line in lines)
        base_container_handled_in_section = False

        if not variation_section_found_cfg:
            self.log("[VARIATION] section not found. Adding it with base_container.", "INFO") # English
            version_idx = -1
            for i, line in enumerate(lines):
                if line.strip().lower() == '[version]': version_idx = i; break
            
            line_ending = '\r\n' if lines and (lines[0].endswith('\r\n') or lines[-1].endswith('\r\n')) else '\n'
            new_variation_lines = [f"{line_ending if version_idx != -1 and lines[version_idx].strip() else ''}[VARIATION]{line_ending}", 
                                   f"    {target_bc_line_content}{line_ending}"]
            if version_idx != -1:
                insert_at = version_idx + 1
                while insert_at < len(lines) and (not lines[insert_at].strip() or not lines[insert_at].strip().startswith('[')):
                    insert_at += 1
                output_lines = lines[:insert_at] + new_variation_lines + [line_ending] + lines[insert_at:]
            else: output_lines = new_variation_lines + [line_ending] + lines 
            needs_rewrite = True
        else:
            in_variation_now = False
            for line in lines:
                s_line = line.strip()
                indent = line[:len(line)-len(line.lstrip())]
                current_eol = '\r\n' if line.endswith('\r\n') else '\n'

                if s_line.lower() == '[variation]':
                    in_variation_now = True; output_lines.append(line); continue
                
                if in_variation_now:
                    if s_line.startswith('['): # Next section
                        if not base_container_handled_in_section:
                            pref_indent = "    " # Default indent
                            if output_lines and output_lines[-1].strip() and not output_lines[-1].strip().startswith('['):
                                pref_indent = output_lines[-1][:len(output_lines[-1]) - len(output_lines[-1].lstrip())] or pref_indent
                            output_lines.append(f"{pref_indent}{target_bc_line_content}{current_eol}")
                            needs_rewrite = True; self.log("Added missing base_container line to existing [VARIATION] section.", "INFO") # English
                        base_container_handled_in_section = True; in_variation_now = False
                        output_lines.append(line); continue
                    
                    if re.match(r'^\s*base_container\s*=', s_line, re.IGNORECASE):
                        base_container_handled_in_section = True
                        if s_line != target_bc_line_content: # Compare exact content for change
                            output_lines.append(f"{indent}{target_bc_line_content}{current_eol}")
                            self.log(f"Updated base_container line. Old: '{s_line}', New: '{target_bc_line_content}'", "INFO") # English
                            needs_rewrite = True
                        else: output_lines.append(line)
                        continue
                output_lines.append(line)
            
            if in_variation_now and not base_container_handled_in_section: # EOF reached while still in [VARIATION]
                pref_indent = "    "
                if output_lines and output_lines[-1].strip() and not output_lines[-1].strip().startswith('['):
                     pref_indent = output_lines[-1][:len(output_lines[-1]) - len(output_lines[-1].lstrip())] or pref_indent
                output_lines.append(f"{pref_indent}{target_bc_line_content}{current_eol if output_lines else '\n'}")
                needs_rewrite = True; self.log("Added base_container at the end of [VARIATION] section (EOF).", "INFO") # English
        
        if needs_rewrite:
            with open(cfg_path, 'w', encoding='utf-8', errors='ignore', newline='') as f_w: f_w.writelines(output_lines)
            self.log(f"aircraft.cfg '{cfg_path.name}' updated successfully.", "SUCCESS") # English
        else: self.log(f"No modifications needed for aircraft.cfg '{cfg_path.name}'.", "DETAIL") # English

    def _generate_layout_file(self, package_root_path: Path) -> tuple[bool, str, int, int]:
        self.log(f"Starting _generate_layout_file for: {package_root_path}", "STEP") # English
        content_entries = []
        files_scanned_count = 0
        content_total_size = 0
        layout_file_size = 0
        manifest_size_at_scan_time = 0
        layout_json_path = package_root_path / "layout.json"
        manifest_json_path = package_root_path / "manifest.json"
        log_interval = 200 

        self.log(f"Scanning package content at '{package_root_path}'...", "INFO") # English
        try:
            if manifest_json_path.is_file():
                try: manifest_size_at_scan_time = manifest_json_path.stat().st_size
                except OSError as e: self.log(f"Warning: Could not get size of {manifest_json_path.name}: {e}", "WARNING") # English

            for root_str, dirs, files in os.walk(str(package_root_path)):
                current_root_path = Path(root_str)
                dirs[:] = [d for d in dirs if not d.startswith("__temp_")] # Exclude own temp folders
                
                rel_root = current_root_path.relative_to(package_root_path) if current_root_path != package_root_path else Path(".")
                self.log(f"  Scanning dir: .\\{rel_root} ({len(files)} files)", "DETAIL") # English
                
                for file_idx, filename in enumerate(files):
                    files_scanned_count += 1
                    if files_scanned_count > 0 and files_scanned_count % log_interval == 0 : # Log progress
                        self.log(f"    ... {files_scanned_count} files scanned so far...", "DETAIL") # English

                    file_abs_path = current_root_path / filename
                    try:
                        rel_path_str = file_abs_path.relative_to(package_root_path).as_posix()
                        if rel_path_str.lower() in ('layout.json', 'manifest.json') or \
                           rel_path_str.lower().startswith('_cvt_') or \
                           filename.startswith('.') or filename.lower() == 'thumbs.db':
                            continue
                        
                        file_stat = file_abs_path.stat()
                        content_entries.append({
                            "path": rel_path_str, "size": file_stat.st_size,
                            "date": _unix_to_filetime(file_stat.st_mtime)
                        })
                        content_total_size += file_stat.st_size
                    except FileNotFoundError:
                        self.log(f"Warning (FileNotFound): '{file_abs_path}' disappeared during scan. Skipping.", "WARNING") # English
                    except Exception as e_file:
                        self.log(f"Warning: Error processing file '{file_abs_path}' for layout: {e_file}. Skipping.", "WARNING") # English
            
            self.log(f"Directory scan complete. {len(content_entries)} files to include in layout.json.", "INFO") # English
            self.log(f"Total content size (excluding layout/manifest): {content_total_size} bytes", "DETAIL") # English

            content_entries.sort(key=lambda x: x['path'])
            with open(layout_json_path, 'w', encoding='utf-8', newline='\n') as f_out:
                json.dump({"content": content_entries}, f_out, indent=4)
            self.log(f"{layout_json_path.name} generated/updated successfully.", "SUCCESS") # English
            try: layout_file_size = layout_json_path.stat().st_size
            except OSError as e: self.log(f"Warning: Could not get size of {layout_json_path.name}: {e}", "WARNING") # English
            return True, "", content_total_size, layout_file_size
        except Exception as e_main:
            err_msg = f"CRITICAL error during layout.json generation for '{package_root_path}': {e_main}" # English
            self.log(err_msg, "ERROR"); import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "DETAIL")
            return False, str(e_main), 0, 0

    def _update_manifest_file(self, manifest_path: Path, total_package_size: int) -> bool:
        self.log(f"Starting _update_manifest_file for: {manifest_path} with total size: {total_package_size}", "STEP") # English
        try:
            if not manifest_path.is_file():
                self.log(f"Error: {manifest_path.name} not found. Cannot update size.", "ERROR"); return False # English
            
            self.log(f"Reading {manifest_path.name} to update size...", "DETAIL") # English
            with open(manifest_path, 'r+', encoding='utf-8') as f:
                manifest_data = json.load(f)
                if not isinstance(manifest_data, dict):
                    self.log(f"Error: {manifest_path.name} is not valid JSON.", "ERROR"); return False # English

                new_size_str = f"{total_package_size:020d}"
                current_size_str = manifest_data.get('total_package_size', '')
                
                if current_size_str != new_size_str:
                    manifest_data['total_package_size'] = new_size_str
                    self.log(f"'total_package_size' in {manifest_path.name} will be updated.", "INFO") # English
                    self.log(f"  Old size: {current_size_str}, New size: {new_size_str} ({total_package_size} bytes)", "DETAIL") # English
                    
                    f.seek(0)
                    json.dump(manifest_data, f, indent=4)
                    f.truncate()
                    self.log(f"Size changes saved successfully to {manifest_path.name}.", "SUCCESS") # English
                else:
                    self.log(f"Info: total_package_size ({current_size_str}) is already correct in {manifest_path.name}. No changes needed.", "DETAIL") # English
            return True
        except json.JSONDecodeError as e_json:
            self.log(f"CRITICAL Error: Could not decode JSON from {manifest_path}: {e_json}", "ERROR") # English
            return False
        except IOError as e_io:
            self.log(f"CRITICAL I/O Error processing {manifest_path}: {e_io}", "ERROR") # English
            return False
        except Exception as e_gen:
            self.log(f"CRITICAL unexpected error updating {manifest_path.name}: {e_gen}", "ERROR") # English
            import traceback
            self.log(f"Traceback _update_manifest_file: {traceback.format_exc()}", "DETAIL")
            return False

    def show_multi_final_message(self, results: list[dict], layout_manifest_pkg_success: bool, layout_manifest_pkg_detail: str, install_path_str: str):
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count
        total_processed_archives = len(results)
        
        title = "Installation Result" # English
        summary_lines = []
        log_level_for_summary = "INFO"
        messagebox_type = messagebox.showinfo

        if total_processed_archives == 0:
            summary_lines.append("No livery archive files were selected or processed.") # English
        elif fail_count == 0 : 
            if layout_manifest_pkg_success:
                summary_lines.append(f"{success_count}/{total_processed_archives} livery(s) installed and package layout/manifest generated successfully!") # English
                summary_lines.append(f"\nLivery Package: {Path(install_path_str).name}") # English
                summary_lines.append("\nThe livery/liveries should now be available in MSFS.") # English
                summary_lines.append("(Restart MSFS if it was running).") # English
                log_level_for_summary = "SUCCESS"
            else: 
                summary_lines.append(f"{success_count}/{total_processed_archives} livery(s) copied successfully, BUT package layout.json generation or manifest.json update failed!") # English
                summary_lines.append(f"\nPackage Error: {layout_manifest_pkg_detail}") # English
                summary_lines.append("\nLiveries might NOT appear in MSFS or the package could be corrupted. Check the log and Help tab.") # English
                log_level_for_summary = "WARNING"
                messagebox_type = messagebox.showwarning
        else: 
            summary_lines.append(f"Installation completed with {fail_count} error(s) out of {total_processed_archives} archive(s) processed.") # English
            summary_lines.append(f" - Successful liveries/archives: {success_count}") # English
            summary_lines.append(f" - Failed liveries/archives: {fail_count}") # English
            
            summary_lines.append(f"\nPackage Layout/Manifest Status: {layout_manifest_pkg_detail if layout_manifest_pkg_detail else 'Update not attempted due to prior errors.'}") # English
            
            summary_lines.append("\nDetails for failed items (check log for more info):") # English
            errors_shown_count = 0
            max_errors_to_display_in_box = 3
            for result_item in results:
                if not result_item["success"] and errors_shown_count < max_errors_to_display_in_box:
                    error_text = result_item['detail']
                    if len(error_text) > 120: error_text = error_text[:117] + "..."
                    summary_lines.append(f" - {Path(result_item['file']).name}: {error_text}")
                    errors_shown_count += 1
            if fail_count > max_errors_to_display_in_box:
                summary_lines.append(f"    (... and {fail_count - max_errors_to_display_in_box} more errors. Check log.)") # English
            
            log_level_for_summary = "ERROR"
            messagebox_type = messagebox.showerror

        final_summary_message = "\n".join(summary_lines)
        self.log(f"FINAL SUMMARY: {final_summary_message.replace('\n', ' :: ')}", log_level_for_summary) # Corrected replace
        
        messagebox_type(title, final_summary_message)

    def on_close(self):
        self.log("Saving configuration on exit...", "DETAIL") # English
        try:
            self.save_config()
        except Exception as e:
            self.log(f"Error saving configuration during exit: {e}", "WARNING") # English
        finally:
            self.master.destroy()

# --- Main Execution ---
def main():
    try:
        from ctypes import windll, wintypes
        try: 
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = wintypes.HANDLE(-4)
            windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        except (AttributeError, OSError):
            try: windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                try: windll.user32.SetProcessDPIAware()
                except (AttributeError, OSError): print("Warning: Could not set DPI awareness.") # English
    except ImportError: pass 
    except Exception as e_dpi: print(f"Error setting DPI awareness: {e_dpi}") # English

    root = tk.Tk()
    app = PMDGLiveryInstaller(root)
    root.mainloop()

if __name__ == "__main__":
    main()
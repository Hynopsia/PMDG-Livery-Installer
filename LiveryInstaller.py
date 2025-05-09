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
import configparser
from datetime import datetime
import threading
import tempfile
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
DEFAULT_MIN_GAME_VERSION = "1.37.19"
PTP_CONVERTER_EXE_NAME = "ptp_converter.exe"

# Base folder names in Community for livery packages
VARIANT_PACKAGE_MAP = {
    # PMDG 777
    "777-200ER": "pmdg-aircraft-77er-liveries",
    "777-300ER": "pmdg-aircraft-77w-liveries",
    "777F": "pmdg-aircraft-77f-liveries",
    # PMDG 737
    "737-600": "pmdg-aircraft-736-liveries",
    "737-700": "pmdg-aircraft-737-liveries",
    "737-700BBJ": "pmdg-aircraft-737-liveries",
    "737-700BDSF": "pmdg-aircraft-737-liveries",
    "737-800": "pmdg-aircraft-738-liveries",
    "737-800BBJ2": "pmdg-aircraft-738-liveries",
    "737-800BCF": "pmdg-aircraft-738-liveries",
    "737-800BDSF": "pmdg-aircraft-738-liveries",
    "737-900": "pmdg-aircraft-739-liveries",
    "737-900ER": "pmdg-aircraft-739-liveries",
}

# Base aircraft folder names inside SimObjects/Airplanes
VARIANT_BASE_AIRCRAFT_MAP = {
    # PMDG 777
    "777-200ER": "PMDG 777-200ER",
    "777-300ER": "PMDG 777-300ER",
    "777F": "PMDG 777F",
    # PMDG 737
    "737-600": "PMDG 737-600",
    "737-700": "PMDG 737-700",
    "737-700BBJ": "PMDG 737-700BBJ",
    "737-700BDSF": "PMDG 737-700BDSF",
    "737-800": "PMDG 737-800",
    "737-800BBJ2": "PMDG 737-800BBJ2",
    "737-800BCF": "PMDG 737-800BCF",
    "737-800BDSF": "PMDG 737-800BDSF",
    "737-900": "PMDG 737-900",
    "737-900ER": "PMDG 737-900ER",
}

EXPECTED_PMDG_BASE_PACKAGE_NAMES = {
    "pmdg-aircraft-77er", "pmdg-aircraft-77w", "pmdg-aircraft-77f",
    "pmdg-aircraft-736", "pmdg-aircraft-737",
    "pmdg-aircraft-738", "pmdg-aircraft-739",
}

# Map selected aircraft variant code to the required base PMDG package dependency name (for manifest.json)
VARIANT_DEPENDENCY_MAP = {
    # PMDG 777
    "777-200ER": "pmdg-aircraft-77er",
    "777-300ER": "pmdg-aircraft-77w",
    "777F": "pmdg-aircraft-77f",

    # PMDG 737
    "737-600": "pmdg-aircraft-736",  

    "737-700": "pmdg-aircraft-737",      
    "737-700BBJ": "pmdg-aircraft-737",   
    "737-700BDSF": "pmdg-aircraft-737", 

    "737-800": "pmdg-aircraft-738",      
    "737-800BBJ2": "pmdg-aircraft-738",  
    "737-800BCF": "pmdg-aircraft-738",   
    "737-800BDSF": "pmdg-aircraft-738", 

    "737-900": "pmdg-aircraft-739",      
    "737-900ER": "pmdg-aircraft-739",    
}

AIRCRAFT_CFG_BASE_CONTAINER_MAP = {
    "777-200ER": "PMDG 777-200ER", "777-300ER": "PMDG 777-300ER", "777F": "PMDG 777F",
    "737-600": "PMDG 737-600",
    "737-700": "PMDG 737-700", "737-700BBJ": "PMDG 737-700BBJ", "737-700BDSF": "PMDG 737-700BDSF",
    "737-800": "PMDG 737-800", "737-800BBJ2": "PMDG 737-800BBJ2", "737-800BCF": "PMDG 737-800BCF", "737-800BDSF": "PMDG 737-800BDSF",
    "737-900": "PMDG 737-900", "737-900ER": "PMDG 737-900ER",
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
    AIRCRAFT_HIERARCHY = {
        "Boeing 777": ["777-200ER", "777-300ER", "777F"],
        "Boeing 737 NG": [
            "737-600",
            "737-700", "737-700BBJ", "737-700BDSF",
            "737-800", "737-800BBJ2", "737-800BCF", "737-800BDSF",
            "737-900", "737-900ER"
        ]
    }

    def __init__(self, master: tk.Tk):
        self.master = master
        self.app_version = "v2.1.1" # Reflects 737 support and UI improvement
        master.title(f"PMDG 737 & 777 Livery Installer {self.app_version}")
        master.geometry("850x750") # Adjusted geometry
        master.minsize(750, 650) # Adjusted min height

        icon_path_rel = "icon.ico"
        try:
            icon_path_abs = get_resource_path(icon_path_rel)
            if os.path.exists(icon_path_abs): master.iconbitmap(icon_path_abs)
            else: print(f"Warning: Icon file not found at {icon_path_abs}")
        except Exception as e: print(f"Warning: Could not set window icon: {e}")

        self.ptp_converter_exe = get_resource_path(PTP_CONVERTER_EXE_NAME)
        if not os.path.exists(self.ptp_converter_exe):
            print(f"CRITICAL WARNING: {PTP_CONVERTER_EXE_NAME} not found. PTP functionality will be unavailable.")
            self.ptp_converter_exe = None

        self.selected_zip_files: list[str] = []

        self.bg_color = "#f0f0f0"; self.header_bg = "#1a3f5c"; self.header_fg = "white"
        self.button_color = "#2c5f8a"; self.button_hover = "#3d7ab3"; self.accent_color = "#007acc"
        self.success_color = "dark green"; self.warning_color = "orange"; self.error_color = "red"

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
        self.style.configure("TCombobox", padding=5, font=("Arial", 10))
        self.style.configure("TNotebook", background=self.bg_color)
        self.style.configure("TNotebook.Tab", padding=[10, 5], font=("Arial", 10))

        main_container = ttk.Frame(master, style="TFrame")
        main_container.pack(fill=tk.BOTH, expand=True)

        header_frame = ttk.Frame(main_container, style="Header.TFrame")
        header_frame.pack(fill=tk.X)
        title_frame = ttk.Frame(header_frame, style="Header.TFrame")
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)
        ttk.Label(title_frame, text="PMDG 737 & 777 Livery Installation Tool", style="Header.TLabel").pack(side=tk.TOP, anchor=tk.W)
        ttk.Label(title_frame, text="Install liveries for PMDG 737 & 777, and generate layout.json", foreground="light gray", background=self.header_bg, font=("Arial", 10)).pack(side=tk.TOP, anchor=tk.W, pady=(0, 5))

        self.main_frame = ttk.Frame(main_container, padding="20", style="TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(self.main_frame, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        setup_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(setup_tab, text="  Setup  ")
        install_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(install_tab, text="  Install Livery(s)  ")
        help_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(help_tab, text="  Help  ")

        self.aircraft_series_var = tk.StringVar()
        self.aircraft_variant_var = tk.StringVar()

        self._setup_setup_tab(setup_tab)
        self._setup_install_tab(install_tab)
        self._setup_help_tab(help_tab)

        status_frame = ttk.Frame(main_container, relief=tk.SUNKEN, borderwidth=1)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W, background='').pack(side=tk.LEFT, padx=10, pady=3)
        ttk.Label(status_frame, text=self.app_version, style="Status.TLabel", anchor=tk.E, background='').pack(side=tk.RIGHT, padx=10, pady=3)

        self.load_config()
        master.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_setup_tab(self, parent: ttk.Frame):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Configuration Settings", style="Subheader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))

        ttk.Label(parent, text="MSFS Community Folder:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.community_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.community_path_var, width=60).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Button(parent, text="Browse...", command=self.select_community_folder).grid(row=1, column=2, padx=5, pady=5)
        ttk.Label(parent, text="Location of your MSFS add-ons (Community folder).", style="Info.TLabel").grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=5)
        ttk.Button(parent, text="Find Common Locations", command=self.show_common_locations).grid(row=2, column=0, sticky=tk.W, padx=5)

        pmdg_path_frame = ttk.LabelFrame(parent, text="PMDG Aircraft Base Package Paths (LocalState/packages - for .ini files)", padding=10)
        pmdg_path_frame.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(20, 5))
        pmdg_path_frame.columnconfigure(1, weight=1)

        self.pmdg_77er_path_var = tk.StringVar(); self.pmdg_77w_path_var = tk.StringVar(); self.pmdg_77f_path_var = tk.StringVar()
        self.pmdg_736_path_var = tk.StringVar(); self.pmdg_737_path_var = tk.StringVar()
        self.pmdg_738_path_var = tk.StringVar(); self.pmdg_739_path_var = tk.StringVar()

        paths_to_setup = [
            ("777-200ER Path:", self.pmdg_77er_path_var, "pmdg-aircraft-77er"),
            ("777-300ER Path:", self.pmdg_77w_path_var, "pmdg-aircraft-77w"),
            ("777F Path:", self.pmdg_77f_path_var, "pmdg-aircraft-77f"),
            ("737-600 Path:", self.pmdg_736_path_var, "pmdg-aircraft-736"),
            ("737-700 (Base) Path:", self.pmdg_737_path_var, "pmdg-aircraft-737"),
            ("737-800 (Base) Path:", self.pmdg_738_path_var, "pmdg-aircraft-738"),
            ("737-900 (Base) Path:", self.pmdg_739_path_var, "pmdg-aircraft-739"),
        ]

        for i, (label_text, var, expected_prefix) in enumerate(paths_to_setup):
            ttk.Label(pmdg_path_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, padx=5, pady=3)
            ttk.Entry(pmdg_path_frame, textvariable=var, width=55).grid(row=i, column=1, sticky=tk.EW, pady=3)
            ttk.Button(pmdg_path_frame, text="Browse...", command=lambda v=var, p=expected_prefix: self.select_pmdg_package_folder(v, p)).grid(row=i, column=2, padx=5, pady=3)

        current_row_after_paths_in_frame = len(paths_to_setup)
        ttk.Label(pmdg_path_frame,
                  text="Path to the PMDG aircraft BASE package (e.g., 'pmdg-aircraft-77er', 'pmdg-aircraft-737-600') in '...\\LocalState\\packages'. Used for .ini handling.",
                  style="Info.TLabel", wraplength=550, justify=tk.LEFT).grid(row=current_row_after_paths_in_frame, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(5,0))
        
        # Corrected row placement for elements after pmdg_path_frame
        # pmdg_path_frame is at parent grid row 3.
        # Next available row in parent grid is 4.
        reference_row_start_in_parent = 4
        ttk.Label(parent, text="Reference PMDG Livery Folder:").grid(row=reference_row_start_in_parent, column=0, sticky=tk.W, padx=5, pady=(20, 5))
        self.reference_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.reference_path_var, width=60).grid(row=reference_row_start_in_parent, column=1, sticky=tk.EW, pady=(20, 5))
        ttk.Button(parent, text="Browse...", command=self.select_reference_folder).grid(row=reference_row_start_in_parent, column=2, padx=5, pady=(20, 5))
        ttk.Label(parent, text="Any installed PMDG 777 or 737 livery folder (for manifest/layout templates).", style="Info.TLabel").grid(row=reference_row_start_in_parent + 1, column=1, columnspan=2, sticky=tk.W, padx=5)

        save_button_row_in_parent = reference_row_start_in_parent + 2
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=save_button_row_in_parent, column=0, columnspan=3, sticky=tk.EW, pady=25)
        ttk.Button(parent, text="Save Settings", command=self.save_config).grid(row=save_button_row_in_parent + 1, column=0, columnspan=3, pady=10)

    def _on_series_select(self, event=None):
        selected_series = self.aircraft_series_var.get()
        variants = self.AIRCRAFT_HIERARCHY.get(selected_series, [])
        
        self.variant_combobox['values'] = variants
        if variants:
            self.aircraft_variant_var.set("") 
            self.variant_combobox.set("") # Clear visual selection
            self.variant_combobox.current(0) 
            self.aircraft_variant_var.set(self.variant_combobox.get()) 
            self.variant_combobox.config(state='readonly')
        else:
            self.aircraft_variant_var.set("")
            self.variant_combobox.set("")
            self.variant_combobox.config(state='disabled')
        self.log(f"Aircraft series selected: {selected_series}. Variants available: {len(variants)}", "DETAIL")

    def _setup_install_tab(self, parent: ttk.Frame):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Install New Livery(s)", style="Subheader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))

        current_row = 1
        ttk.Label(parent, text="Livery File(s):").grid(row=current_row, column=0, sticky=tk.W, padx=5, pady=5)
        self.livery_zip_display_var = tk.StringVar()
        self.livery_zip_entry = ttk.Entry(parent, textvariable=self.livery_zip_display_var, width=60, state='readonly')
        self.livery_zip_entry.grid(row=current_row, column=1, sticky=tk.EW, pady=5)
        ttk.Button(parent, text="Browse...", command=self.select_livery_files).grid(row=current_row, column=2, padx=5, pady=5)
        current_row += 1
        ttk.Label(parent, text="Select one or more archive files (.zip or .ptp).", style="Info.TLabel").grid(row=current_row, column=1, sticky=tk.W, padx=5)
        current_row += 1
        ttk.Label(parent, text="IMPORTANT! If selecting multiple files, they MUST be for the SAME aircraft variant.", style="Warn.Info.TLabel").grid(row=current_row, column=1, columnspan=2, sticky=tk.W, padx=5)
        current_row += 1

        aircraft_selection_frame = ttk.LabelFrame(parent, text="Aircraft Model & Variant", padding=10)
        aircraft_selection_frame.grid(row=current_row, column=0, columnspan=3, sticky=tk.EW, pady=(20,5), padx=5)
        aircraft_selection_frame.columnconfigure(1, weight=1)
        
        ttk.Label(aircraft_selection_frame, text="Aircraft Series:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.series_combobox = ttk.Combobox(aircraft_selection_frame, textvariable=self.aircraft_series_var,
                                            values=list(self.AIRCRAFT_HIERARCHY.keys()), state='readonly', width=30, style="TCombobox")
        self.series_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        self.series_combobox.bind("<<ComboboxSelected>>", self._on_series_select)

        ttk.Label(aircraft_selection_frame, text="Variant/Sub-Model:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.variant_combobox = ttk.Combobox(aircraft_selection_frame, textvariable=self.aircraft_variant_var,
                                             state='disabled', width=30, style="TCombobox")
        self.variant_combobox.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        current_row += 1 # For the LabelFrame

        ttk.Label(parent, text="Select the aircraft series first, then the specific variant.", style="Info.TLabel").grid(row=current_row, column=1, columnspan=2, sticky=tk.W, padx=5, pady=(0,10))
        current_row +=1

        ttk.Label(parent, text="Livery Name (in-sim):").grid(row=current_row, column=0, sticky=tk.W, padx=5, pady=(15, 5))
        self.custom_name_var = tk.StringVar()
        self.custom_name_entry = ttk.Entry(parent, textvariable=self.custom_name_var, width=60)
        self.custom_name_entry.grid(row=current_row, column=1, sticky=tk.EW, pady=(15, 5))
        current_row +=1
        ttk.Label(parent, text="Optional. Ignored if multiple files selected (auto-detected from archive/aircraft.cfg).", style="Info.TLabel").grid(row=current_row, column=1, columnspan=2, sticky=tk.W, padx=5)
        current_row +=1

        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=current_row, column=0, columnspan=3, sticky=tk.EW, pady=20)
        current_row +=1
        
        action_frame_row = current_row # Save the row where action_frame is placed
        action_frame = ttk.Frame(parent, style="TFrame")
        action_frame.grid(row=action_frame_row, column=0, columnspan=3, sticky=tk.NSEW, pady=10)
        action_frame.columnconfigure(0, weight=1)
        action_frame.rowconfigure(2, weight=1)

        self.install_button = ttk.Button(action_frame, text="Install Livery(s) & Generate Layout", command=self.start_install_thread, style="Accent.TButton")
        self.install_button.grid(row=0, column=0, pady=(0, 15))

        progress_frame = ttk.Frame(action_frame, style="TFrame")
        progress_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        progress_frame.columnconfigure(1, weight=1)
        ttk.Label(progress_frame, text="Progress:").grid(row=0, column=0, sticky=tk.W)
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, style="Horizontal.TProgressbar")
        self.progress.grid(row=0, column=1, sticky=tk.EW, padx=5)

        log_frame = ttk.LabelFrame(action_frame, text="Installation Log", style="TLabelframe")
        log_frame.grid(row=2, column=0, sticky=tk.NSEW)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=10, width=80, wrap=tk.WORD, bd=0, font=("Courier New", 9), relief=tk.FLAT, background="white")
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

        parent.rowconfigure(action_frame_row, weight=1)

    def get_eol_char(self, lines: list[str]) -> str:
        """Determines the EOL character from a list of lines."""
        if lines and lines[0].endswith('\r\n'):
            return '\r\n'
        return '\n'
    
    def _add_texture_fallback_if_needed(self,
                                        current_livery_texture_folder_path: Path,
                                        base_livery_simobjects_folder_name: str,
                                        base_livery_texture_folder_name: str,
                                        original_cfg_lines_for_eol: list[str] | None):
        """
        Adds a fallback entry to the texture.cfg of the current livery, pointing to the base livery's textures.
        It tries to insert as fallback.1, shifting others down.
        """
        texture_cfg_path = current_livery_texture_folder_path / "texture.cfg"
        if not texture_cfg_path.is_file():
            self.log(f"Cannot add fallback: texture.cfg not found in '{current_livery_texture_folder_path}'. Livery might be self-contained or use global fallbacks.", "DETAIL")
            return

        # Construct the relative path from the current livery's texture folder to the base livery's texture folder
        # Assumes SimObjects/Airplanes/[LiveryFolderName]/[TextureFolderName] structure
        relative_fallback_path = f"..\\..\\{base_livery_simobjects_folder_name}\\{base_livery_texture_folder_name}"
        
        self.log(f"Attempting to add fallback to '{relative_fallback_path}' in '{texture_cfg_path}'", "INFO")

        try:
            with open(texture_cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            eol = self.get_eol_char(lines if lines else (original_cfg_lines_for_eol or ['\n']))

            output_lines = []
            fltsim_section_found = False
            fallback_entry_to_add = f"fallback.1={relative_fallback_path}"
            
            # Check if this exact fallback already exists (naively)
            if any(relative_fallback_path in line for line in lines):
                self.log(f"Fallback to '{relative_fallback_path}' seems to already exist or is similar in {texture_cfg_path}. Skipping addition.", "DETAIL")
                return

            temp_fallbacks = {} # To store existing fallbacks and re-number them
            new_lines_for_section = []
            in_fltsim_section_for_processing = False

            for line in lines:
                stripped_line = line.strip()
                s_line_lower = stripped_line.lower()

                if s_line_lower == "[fltsim]":
                    fltsim_section_found = True
                    in_fltsim_section_for_processing = True
                    new_lines_for_section.append(line)
                    continue
                elif stripped_line.startswith("[") and in_fltsim_section_for_processing:
                    # End of [fltsim] section
                    in_fltsim_section_for_processing = False
                    # Add stored fallbacks before appending the current line (which starts a new section)
                    # Add the new primary fallback first
                    new_lines_for_section.append(fallback_entry_to_add + eol)
                    # Add re-numbered existing fallbacks
                    for i in sorted(temp_fallbacks.keys()):
                        new_lines_for_section.append(f"fallback.{i + 1}={temp_fallbacks[i]}{eol}")
                    temp_fallbacks.clear() # Clear for next potential section (though unlikely for texture.cfg)
                    output_lines.extend(new_lines_for_section)
                    new_lines_for_section = []
                    output_lines.append(line) # Current line starting new section
                elif in_fltsim_section_for_processing:
                    fallback_match = re.match(r"fallback\.([0-9]+)\s*=\s*(.*)", stripped_line, re.IGNORECASE)
                    if fallback_match:
                        idx = int(fallback_match.group(1))
                        val = fallback_match.group(2)
                        temp_fallbacks[idx] = val # Store existing fallbacks
                        # Don't add to new_lines_for_section yet, will be re-added re-numbered
                    else:
                        new_lines_for_section.append(line) # Non-fallback line within [fltsim]
                else:
                    output_lines.append(line) # Line outside any [fltsim] section processing

            # If [fltsim] was the last section or file ended within it
            if in_fltsim_section_for_processing:
                new_lines_for_section.append(fallback_entry_to_add + eol)
                for i in sorted(temp_fallbacks.keys()):
                    new_lines_for_section.append(f"fallback.{i + 1}={temp_fallbacks[i]}{eol}")
                output_lines.extend(new_lines_for_section)
            
            if not fltsim_section_found: # If no [fltsim] section at all, create it with the new fallback
                if output_lines and output_lines[-1].strip() != "": output_lines.append(eol) # Blank line if needed
                output_lines.append(f"[fltsim]{eol}")
                output_lines.append(fallback_entry_to_add + eol)
                self.log(f"Created [fltsim] section and added fallback to {texture_cfg_path}", "INFO")
            elif not (fallback_entry_to_add + eol in new_lines_for_section or fallback_entry_to_add + eol in output_lines):
                 # This case should be covered by the logic above, but as a safeguard
                 self.log(f"Fallback was not added as expected, verify logic. File: {texture_cfg_path}", "WARNING")


            with open(texture_cfg_path, 'w', encoding='utf-8', errors='ignore', newline='') as f_w:
                f_w.writelines(output_lines)
            self.log(f"Successfully updated texture.cfg: {texture_cfg_path} with fallback to {base_livery_simobjects_folder_name}", "SUCCESS")

        except Exception as e:
            self.log(f"Error modifying texture.cfg at {texture_cfg_path}: {e}", "ERROR")
            import traceback
            self.log(f"Traceback for texture.cfg modification: {traceback.format_exc()}", "DETAIL")

    def _setup_help_tab(self, parent: ttk.Frame):
        help_canvas = tk.Canvas(parent, highlightthickness=0, background=self.bg_color)
        help_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=help_canvas.yview)
        scrollable_frame = ttk.Frame(help_canvas, style="TFrame")
        
        scrollable_frame.bind("<Configure>", lambda e: help_canvas.configure(scrollregion=help_canvas.bbox("all")))
        canvas_window = help_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        help_canvas.configure(yscrollcommand=help_scrollbar.set)
        
        def rebind_wraplength(event):
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
        
        def add_section_header(text): nonlocal current_row; lbl = ttk.Label(scrollable_frame, text=text, style="Subheader.TLabel"); lbl.grid(row=current_row, column=0, sticky="w", pady=(15, 5)); lbl._original_indent = 0; current_row += 1
        def add_text(text, indent=0, style="TLabel"): nonlocal current_row; lbl = ttk.Label(scrollable_frame, text=text, justify=tk.LEFT, style=style, background=self.bg_color); lbl.grid(row=current_row, column=0, sticky="w", padx=(indent * 20, 0)); lbl._original_indent = indent; current_row += 1
        def add_bold_text(text, indent=0): nonlocal current_row; lbl = ttk.Label(scrollable_frame, text=text, justify=tk.LEFT, font=("Arial", 10, "bold"), background=self.bg_color); lbl.grid(row=current_row, column=0, sticky="w", padx=(indent * 20, 0), pady=(5,0)); lbl._original_indent = indent; current_row += 1

        # --- Help Content (English) - Needs further review and updates for 737 specifics ---
        add_section_header("Quick Start Guide")
        add_text("1. Go to the Setup tab:")
        add_text("- Select your MSFS Community folder.", indent=1)
        add_text("- Set the 'PMDG Aircraft Base Package Path' for each aircraft type (777s, 737-600, 737-700 Base, etc.) you own. This points to the aircraft's main folder in ...\\LocalState\\packages.", indent=1)
        add_text("- Select any existing installed PMDG 777 or 737 livery folder as a Reference.", indent=1)
        add_text("- Click Save Settings.", indent=1)
        add_text("2. Go to the Install Livery(s) tab:")
        add_text("- Browse for your livery archive file(s) (.zip or .ptp).", indent=1)
        add_text("- Select the Aircraft Series (e.g., Boeing 737 NG), then the specific Variant/Sub-Model (e.g., 737-800BBJ2). This is mandatory!", indent=1)
        add_text("- If selecting multiple files, ensure ALL are for the same variant you chose.", indent=1)
        add_text("- Optionally, enter a Livery Name if you selected a SINGLE file.", indent=1)
        add_text("- Click 'Install Livery(s) & Generate Layout'.", indent=1)
        add_text("3. Check the log for success or errors. The tool will copy files, modify aircraft.cfg, handle .ini files, and automatically generate layout.json.", indent=1)
        add_text("4. Launch MSFS and find your new livery/liveries! (Restart MSFS if it was running).", indent=1)

        add_section_header("Configuration Details")
        add_bold_text("MSFS Community Folder:")
        add_text("This is where MSFS add-ons are installed.", indent=1)
        add_bold_text("PMDG Aircraft Base Package Paths (LocalState):")
        add_text("Path to the specific PMDG aircraft BASE package folder (e.g., 'pmdg-aircraft-77er', 'pmdg-aircraft-737-600') inside the 'packages' folder in your MSFS LocalState. Used for copying renamed .ini files.", indent=1)
        add_bold_text("Reference PMDG Livery Folder:")
        add_text("Needed for copying manifest.json and layout.json templates if the livery package is new. Can be from any PMDG 777 or 737 livery.", indent=1)
        add_bold_text(f"{PTP_CONVERTER_EXE_NAME}:")
        add_text(f"This tool requires '{PTP_CONVERTER_EXE_NAME}' to process .ptp files. Ensure it is in the same folder as this livery installer.", indent=1)
        add_text("If missing, .ptp file installation will fail.", indent=1)
        add_bold_text("Long File Path Handling (Windows):")
        add_text("MSFS and its add-ons can use very long file paths. To ensure this tool can correctly scan all livery files, "
                 "especially during 'layout.json' generation, enabling 'Win32 long paths' in your Windows OS is recommended.", indent=1)
        add_text("Search online for 'Enable Win32 long paths Windows 10/11' for instructions. This application is also packaged to be long-path aware.", indent=1)
        
        add_section_header("Troubleshooting")
        add_bold_text("Livery Not Appearing in MSFS:")
        add_text("- Check the Installation Log for ERROR messages, especially during 'Generating layout.json' or 'Processing options.ini' steps.", indent=1)
        add_text("- Verify that the MSFS Community Folder path is correct in Setup.", indent=1)
        add_text("- Ensure you selected the correct Aircraft Series and Variant during installation.", indent=1) # MODIFIED
        add_text("- Ensure the dependency in the package's manifest.json (e.g., in pmdg-aircraft-77w-liveries) matches the base aircraft (e.g., 'pmdg-aircraft-77w'). The tool attempts to fix this, but check the log.", indent=1)
        add_text("- For 777-200ER, check the log if the correct engine type (GE/RR/PW) was detected and applied to aircraft.cfg.", indent=1)
        add_text("- Verify the 'PMDG Aircraft Base Package Path (LocalState)' for the relevant aircraft type is correct if you expected an .ini file to be copied.", indent=1) # MODIFIED
        add_text("- Restart MSFS. A restart is sometimes needed.", indent=1)
        add_text("- Check the MSFS Content Manager for the livery package.", indent=1)
        add_text("- If layout generation failed or was skipped (see log), new liveries won't appear until this step completes successfully for the entire batch.", indent=1)

        add_bold_text("Installation Errors:")
        add_text("- Ensure the archive file(s) (.zip or .ptp) are not corrupt. ZIPs should contain expected folders (texture.*, model, aircraft.cfg, optionally options.ini or <atc_id>.ini).", indent=1)
        add_text(f"- For .ptp files, ensure {PTP_CONVERTER_EXE_NAME} is functional and in the same folder as this application.", indent=1)
        add_text("- Verify the selected Reference Livery Folder is valid and functional.", indent=1)
        
        add_bold_text("Nested ZIPs:")
        add_text("- The tool attempts to detect and install liveries from ZIP files contained within a primary selected ZIP file (e.g., a 'pack' zip).", indent=1)
        add_text("- Check the log if a 'pack' file fails; it might indicate an unexpected internal structure.", indent=1)
        
        add_bold_text("RAR Files:")
        add_text("- This tool only supports ZIP and PTP (via ptp_converter.exe) archive files.", indent=1)

        add_section_header("About")
        add_text(f"PMDG 737 & 777 Livery Installer {self.app_version}")
        add_text("This tool prepares, copies, and configures livery files for the PMDG 737 & 777 families in MSFS.", style="TLabel")
        add_text(f"It handles folder creation, file extraction (ZIPs, including nested; PTPs using {PTP_CONVERTER_EXE_NAME}), " 
                 "aircraft.cfg modification, options.ini/<atc_id>.ini handling, and automatically generates "
                 "layout.json and updates manifest.json.", style="TLabel")
        add_text("Disclaimer: Use at your own risk. Not affiliated with PMDG or Microsoft.", style="Info.TLabel")

        parent.update_idletasks() 
        for child in scrollable_frame.winfo_children():
            if isinstance(child, ttk.Label) and hasattr(child, '_original_indent'):
                indent_pixels = child._original_indent * 20
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
Check drive settings under the Xbox app, often involves hidden/protected folders like 'WpSystem' or 'WindowsApps'. Access might be restricted.

Finding AppData:
Press Windows Key + R, type `%appdata%` and press Enter to open the Roaming folder.
Press Windows Key + R, type `%localappdata%` and press Enter to open the Local folder.
"""
        location_window = tk.Toplevel(self.master)
        location_window.title("Common Community Folder Locations")
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
        ttk.Button(btn_frame, text="Copy Info to Clipboard", command=lambda: self.copy_to_clipboard(common_locations, location_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=location_window.destroy).pack(side=tk.RIGHT, padx=5)
        location_window.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (location_window.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (location_window.winfo_height() // 2)
        location_window.geometry(f'+{x}+{y}')

    def copy_to_clipboard(self, text: str, parent_window: tk.Toplevel):
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
            self.master.update() # Essential on some systems for clipboard to update
            messagebox.showinfo("Copied", "Locations copied to clipboard.", parent=parent_window)
        except tk.TclError:
            messagebox.showwarning("Clipboard Error", "Could not access the clipboard.", parent=parent_window)

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
            self.log_text.see(tk.END) # Auto-scroll
        except Exception as e:
            print(f"Error logging message: {e}")

    def select_community_folder(self):
        current_path = self.community_path_var.get()
        initial_dir = current_path if Path(current_path).is_dir() else str(Path.home())
        folder = filedialog.askdirectory(title="Select MSFS Community Folder", initialdir=initial_dir)
        if folder:
            self.community_path_var.set(folder)
            self.log(f"Community Folder selected: {folder}", "DETAIL")

    def _get_parent_localstate_packages_path(self) -> Path | None:
        # Try to find the MSFS packages folder where PMDG aircraft base packages are stored
        try:
            local_app_data = os.getenv('LOCALAPPDATA')
            if local_app_data: # MS Store version often here
                packages_dir = Path(local_app_data) / "Packages"
                if packages_dir.is_dir():
                    msfs_pkg_pattern = "Microsoft.FlightSimulator_*_8wekyb3d8bbwe"
                    for item in packages_dir.iterdir():
                        if item.is_dir() and re.match(msfs_pkg_pattern, item.name, re.IGNORECASE):
                            potential_path = item / "LocalState" / "packages" # This is where PMDG base aircraft are
                            if potential_path.is_dir(): return potential_path
            app_data = os.getenv('APPDATA') # Steam version often here
            if app_data:
                steam_msfs_base_path = Path(app_data) / "Microsoft Flight Simulator"
                potential_steam_path = steam_msfs_base_path / "LocalState" / "packages"
                if potential_steam_path.is_dir():
                    return potential_steam_path
        except Exception as e:
            self.log(f"Error trying to auto-detect LocalState packages path: {e}", "DEBUG")
        return Path.home() # Fallback if not found

    def select_pmdg_package_folder(self, target_var: tk.StringVar, expected_folder_prefix: str):
        initial_dir_guess = self._get_parent_localstate_packages_path() or Path.home()
        folder = filedialog.askdirectory(
            title=f"Select PMDG Base Package (e.g., {expected_folder_prefix}) in ...LocalState\\packages",
            initialdir=str(initial_dir_guess)
        )
        if folder:
            p_folder = Path(folder)
            folder_name_lower = p_folder.name.lower()
            if folder_name_lower in EXPECTED_PMDG_BASE_PACKAGE_NAMES:
                if folder_name_lower == expected_folder_prefix.lower():
                    if p_folder.parent and p_folder.parent.name.lower() == 'packages' and \
                       p_folder.parent.parent and p_folder.parent.parent.name.lower() == 'localstate':
                        target_var.set(str(p_folder))
                        self.log(f"PMDG Base Package Path ({expected_folder_prefix}) set: {p_folder}", "DETAIL")
                    else:
                        messagebox.showwarning("Potential Incorrect Path",
                                             f"The folder '{p_folder.name}' is a valid PMDG package, "
                                             f"but it does not appear to be inside a '...\\LocalState\\packages' structure.\n\n"
                                             f"Please ensure this is the correct path for the base aircraft package.")
                        target_var.set(str(p_folder))
                        self.log(f"PMDG Base Package Path ({expected_folder_prefix}) set (Warning: verify 'LocalState\\packages' structure): {p_folder}", "WARNING")
                else:
                    messagebox.showerror("Incorrect Variant/Type",
                                         f"You selected the folder '{p_folder.name}', but a folder named '{expected_folder_prefix}' was expected for this specific input field.\n\n"
                                         f"Please select the correct PMDG base aircraft package folder for this entry.")
                    self.log(f"Incorrect PMDG base package selected for {expected_folder_prefix}. Selected: {folder}", "ERROR")
            else:
                messagebox.showerror("Invalid Folder",
                                     f"The selected folder '{p_folder.name}' does not appear to be a recognized PMDG base aircraft package folder (e.g., {expected_folder_prefix}).\n\n"
                                     f"Please select the correct folder within '...\\LocalState\\packages'.")
                self.log(f"Invalid PMDG Base Package Path selected: {folder}", "ERROR")

    def select_reference_folder(self):
        current_path = self.reference_path_var.get()
        initial_dir = current_path if Path(current_path).is_dir() else \
                      (self.community_path_var.get() if Path(self.community_path_var.get()).is_dir() else str(Path.home()))
        folder = filedialog.askdirectory(title="Select Reference PMDG Livery Folder (737 or 777)", initialdir=initial_dir)
        if folder:
            p_folder = Path(folder)
            if (p_folder / "manifest.json").is_file() and (p_folder / "layout.json").is_file():
                self.reference_path_var.set(str(p_folder))
                self.log(f"Reference livery folder selected: {p_folder}", "DETAIL")
            else:
                missing = [f_name for f_name in ["manifest.json", "layout.json"] if not (p_folder / f_name).is_file()]
                messagebox.showwarning("Invalid Reference", f"The selected folder is missing: {', '.join(missing)}.")
                self.log(f"Invalid reference folder (missing {', '.join(missing)}): {p_folder}", "WARNING")

    def select_livery_files(self):
        initial_dir = str(Path.home() / "Downloads") if (Path.home() / "Downloads").is_dir() else str(Path.home())
        files = filedialog.askopenfilenames(
            title="Select Livery Archive File(s) (.zip or .ptp)",
            filetypes=[
                ("Supported Livery Archives", "*.zip *.ptp"), ("ZIP archives", "*.zip"),
                ("PMDG PTP files", "*.ptp"), ("All files", "*.*")
            ], initialdir=initial_dir
        )
        if files:
            self.selected_zip_files = list(files)
            num_files = len(self.selected_zip_files)
            if num_files == 1:
                display_text = Path(self.selected_zip_files[0]).name
                self.custom_name_entry.config(state=tk.NORMAL)
                self.log(f"Livery file selected: {display_text}", "DETAIL")
                if not self.custom_name_var.get() and \
                   (display_text.lower().endswith((".zip", ".ptp"))):
                    base_name = Path(display_text).stem
                    clean_name = re.sub(r'^(pmdg[-_]?)?(777|737|736|738|739|bbj|bdsf|bcf|er|f|w)?([-_]?(200er|300er|f|w|600|700|800|900|bbj|bbj2|bdsf|bcf|er))?([-_]?)', '', base_name, flags=re.IGNORECASE).strip('-_ ')
                    clean_name = ' '.join(re.sub(r'[-_]+', ' ', clean_name).split()).strip()
                    clean_name = ' '.join(word.capitalize() for word in clean_name.split()) if clean_name else "Unnamed Livery"
                    if clean_name:
                        self.custom_name_var.set(clean_name)
                        self.log(f"Suggested livery name: {clean_name}", "DETAIL")
            else:
                display_text = f"[{num_files} files selected]"
                self.custom_name_var.set("")
                self.custom_name_entry.config(state=tk.DISABLED)
                self.log(f"{num_files} livery files selected.", "INFO")
            self.livery_zip_display_var.set(display_text)
        else:
            self.selected_zip_files = []
            self.livery_zip_display_var.set("")
            self.custom_name_entry.config(state=tk.NORMAL)
            self.log("Livery file selection cancelled.", "DETAIL")

    def save_config(self):
        config = {
            "community_path": self.community_path_var.get(),
            "reference_path": self.reference_path_var.get(),
            "pmdg_77er_path": self.pmdg_77er_path_var.get(), "pmdg_77w_path": self.pmdg_77w_path_var.get(), "pmdg_77f_path": self.pmdg_77f_path_var.get(),
            "pmdg_736_path": self.pmdg_736_path_var.get(), "pmdg_737_path": self.pmdg_737_path_var.get(),
            "pmdg_738_path": self.pmdg_738_path_var.get(), "pmdg_739_path": self.pmdg_739_path_var.get(),
        }
        try:
            config_dir = Path.home() / CONFIG_DIR_NAME
            config_dir.mkdir(parents=True, exist_ok=True)
            with open(config_dir / CONFIG_FILE_NAME, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            self.log("Configuration saved successfully.", "SUCCESS")
            self.status_var.set("Configuration saved")
            self.master.after(2000, lambda: self.status_var.set("Ready"))
        except Exception as e:
            self.log(f"Error saving configuration: {str(e)}", "ERROR")
            messagebox.showerror("Configuration Error", f"Could not save configuration:\n{e}")

    def load_config(self):
        config_path = Path.home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        if config_path.exists():
            try:
                with open(config_path, "r", encoding='utf-8') as f: config_data = json.load(f)
                self.community_path_var.set(config_data.get("community_path", ""))
                self.reference_path_var.set(config_data.get("reference_path", ""))
                self.pmdg_77er_path_var.set(config_data.get("pmdg_77er_path", ""))
                self.pmdg_77w_path_var.set(config_data.get("pmdg_77w_path", ""))
                self.pmdg_77f_path_var.set(config_data.get("pmdg_77f_path", ""))
                self.pmdg_736_path_var.set(config_data.get("pmdg_736_path", ""))
                self.pmdg_737_path_var.set(config_data.get("pmdg_737_path", ""))
                self.pmdg_738_path_var.set(config_data.get("pmdg_738_path", ""))
                self.pmdg_739_path_var.set(config_data.get("pmdg_739_path", ""))
                self.log("Configuration loaded.", "INFO")
            except json.JSONDecodeError as e:
                self.log(f"Error decoding configuration file: {e}. Please review or delete: {config_path}", "ERROR")
                messagebox.showerror("Configuration Error", f"Could not load configuration (invalid JSON):\n{config_path}\nError: {e}")
            except Exception as e:
                self.log(f"Unknown error loading configuration: {e}", "WARNING")
        else:
            self.log("Configuration file not found. Please configure paths in the Setup tab.", "INFO")

    def get_livery_name(self, archive_path_or_folder: Path, temp_extract_dir: Path | None) -> str:
        if temp_extract_dir and temp_extract_dir.is_dir():
            try:
                cfg_path_str = self.find_file_in_dir(temp_extract_dir, "aircraft.cfg")
                if cfg_path_str and Path(cfg_path_str).is_file():
                    with open(cfg_path_str, 'r', encoding='utf-8', errors='ignore') as cfg_file:
                        content = cfg_file.read()
                        fltsim_match = re.search(r'\[FLTSIM\.0\].*?title\s*=\s*"(.*?)"', content, re.DOTALL | re.IGNORECASE)
                        if fltsim_match and fltsim_match.group(1).strip():
                            return fltsim_match.group(1).strip()
                        simple_match = re.search(r'^\s*title\s*=\s*"(.*?)"', content, re.MULTILINE | re.IGNORECASE)
                        if simple_match and simple_match.group(1).strip():
                            return simple_match.group(1).strip()
            except Exception as e: self.log(f"Could not read aircraft.cfg for name detection: {e}", "WARNING")
        
        default_name = Path(archive_path_or_folder).stem
        clean_name = re.sub(r'^(pmdg[-_]?)?(777|737|736|738|739|bbj|bdsf|bcf|er|f|w)?([-_]?(200er|300er|f|w|600|700|800|900|bbj|bbj2|bdsf|bcf|er))?([-_]?)', '', default_name, flags=re.IGNORECASE).strip('-_ ')
        clean_name = ' '.join(re.sub(r'[-_]+', ' ', clean_name).split()).strip()
        return ' '.join(word.capitalize() for word in clean_name.split()) if clean_name else "Unnamed Livery"

    def extract_atc_id(self, cfg_path: Path) -> str | None:
        if not cfg_path.is_file(): return None
        try:
            with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            fltsim0_match = re.search(r'\[fltsim\.0\](.*?)(\n\s*\[|$)', content, re.DOTALL | re.IGNORECASE)
            if fltsim0_match:
                section_content = fltsim0_match.group(1)
                atc_id_match = re.search(r'^\s*atc_id\s*=\s*"?([a-zA-Z0-9_.\- ]+)"?', section_content, re.MULTILINE | re.IGNORECASE)
                if atc_id_match and atc_id_match.group(1).strip():
                    atc_id = atc_id_match.group(1).strip()
                    safe_atc_id = re.sub(r'[\\/*?:"<>|]', '_', atc_id)
                    if safe_atc_id: return safe_atc_id
        except Exception as e: self.log(f"Error extracting ATC ID from {cfg_path}: {e}", "ERROR")
        return None

    def verify_settings(self) -> list[str]:
        errors = []
        community_path = self.community_path_var.get()
        if not community_path: errors.append("- MSFS Community Folder path not set.")
        elif not Path(community_path).is_dir(): errors.append(f"- Community Folder not valid: {community_path}")

        reference_path = self.reference_path_var.get()
        if not reference_path: errors.append("- Reference Livery Folder path not set.")
        elif not Path(reference_path).is_dir(): errors.append(f"- Reference Livery Folder not valid: {reference_path}")
        elif not (Path(reference_path) / "manifest.json").is_file() or not (Path(reference_path) / "layout.json").is_file():
            errors.append(f"- Reference Livery Folder missing manifest.json or layout.json: {reference_path}")

        # CORRECCIÓN AQUÍ: Usar los nombres de paquete base correctos para los 737
        pmdg_base_paths_to_check = {
            "777-200ER": (self.pmdg_77er_path_var.get(), "pmdg-aircraft-77er"),
            "777-300ER": (self.pmdg_77w_path_var.get(), "pmdg-aircraft-77w"),
            "777F": (self.pmdg_77f_path_var.get(), "pmdg-aircraft-77f"),
            "737-600": (self.pmdg_736_path_var.get(), "pmdg-aircraft-736"),  # CORREGIDO
            "737-700 (Base)": (self.pmdg_737_path_var.get(), "pmdg-aircraft-737"),  # CORREGIDO
            "737-800 (Base)": (self.pmdg_738_path_var.get(), "pmdg-aircraft-738"),  # CORREGIDO
            "737-900 (Base)": (self.pmdg_739_path_var.get(), "pmdg-aircraft-739"),  # CORREGIDO
        }
        for label, (path_str, expected) in pmdg_base_paths_to_check.items(): # Renombrado el dict para claridad
            if path_str: # Only validate if user has entered a path
                if not Path(path_str).is_dir(): 
                    errors.append(f"- PMDG {label} Path ('{path_str}') is not a valid directory.")
                elif Path(path_str).name.lower() != expected: 
                    errors.append(f"- PMDG {label} Path folder name should be '{expected}'. Found: {Path(path_str).name}")
        
        selected_variant = self.aircraft_variant_var.get()
        if not selected_variant : 
            errors.append("- Aircraft Variant for installation not selected.")
        # La validación específica de que la ruta para el *selected_variant* esté configurada
        # se hace de forma más directa en start_install_thread antes de iniciar la instalación.
        # verify_settings se enfoca en la validez de las rutas que *están* configuradas.

        if not self.selected_zip_files: 
            errors.append("- No livery archive files (.zip or .ptp) selected.")
        else:
            if any(Path(f).suffix.lower() == ".ptp" for f in self.selected_zip_files) and \
               (not self.ptp_converter_exe or not os.path.exists(self.ptp_converter_exe)):
                errors.append(f"- A .ptp file selected, but '{PTP_CONVERTER_EXE_NAME}' was not found.")
            for f_path_str in self.selected_zip_files:
                f_p = Path(f_path_str)
                if not f_p.is_file(): errors.append(f"- Selected livery file not found: {f_path_str}")
                elif f_p.suffix.lower() not in [".zip", ".ptp"]: errors.append(f"- File '{f_p.name}' is not .zip or .ptp.")
        return errors

    def find_file_in_dir(self, directory: Path, filename_lower: str) -> str | None:
        """Recursively searches for a file (case-insensitive) in a directory."""
        search_path = Path(directory)
        if not search_path.is_dir():
            self.log(f"find_file_in_dir: Provided directory does not exist or is invalid: {search_path}", "WARNING")
            return None
            
        for root, dirs, files in os.walk(search_path):
            # Exclude temp processing folders from search if any (though less likely here)
            dirs[:] = [d for d in dirs if not d.startswith("__temp_")]
            for file_name in files:
                if file_name.lower() == filename_lower:
                    return os.path.join(root, file_name)
        return None

    def find_dir_in_dir(self, directory: Path, dirname_lower: str) -> str | None:
        """Recursively searches for a directory (case-insensitive) in a directory."""
        search_dir = Path(directory)
        if not search_dir.is_dir():
            self.log(f"find_dir_in_dir: Provided directory does not exist or is invalid: {search_dir}", "WARNING")
            return None

        for item in search_dir.iterdir(): # Check top level first
            if item.is_dir() and item.name.lower() == dirname_lower and not item.name.startswith("__temp_"):
                return str(item)
        
        for root, dirs, files in os.walk(search_dir, topdown=True):
            # Exclude temp processing folders from search
            dirs[:] = [d for d in dirs if not d.startswith("__temp_")]
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
            self.log(f"find_texture_dirs_in_dir: Provided directory does not exist or is invalid: {search_dir}", "WARNING")
            return []
            
        try:
            for root_str, dirs, files in os.walk(search_dir):
                # Exclude temp processing folders from search
                dirs[:] = [d for d in dirs if not d.startswith("__temp_")]
                root_path = Path(root_str)
                for d_name in list(dirs): 
                    if d_name.lower().startswith("texture."):
                        full_path_str = str(root_path / d_name)
                        if full_path_str not in texture_dirs: 
                            texture_dirs.append(full_path_str)
        except OSError as e:
            self.log(f"Error traversing directory {search_dir} for texture folders: {e}", "WARNING")
        
        if not texture_dirs:
                self.log(f"No 'texture.*' folders found in {directory}", "DETAIL")
        return texture_dirs

    def start_install_thread(self):
        errors = self.verify_settings()
        
        selected_variant = self.aircraft_variant_var.get()
        if selected_variant: # This check ensures a variant is selected before proceeding
            required_base_pkg_path_str = ""
            path_label_for_error = f"PMDG {selected_variant} Base Package Path" # Default error label

            if selected_variant.startswith("777"):
                if selected_variant == "777-200ER": required_base_pkg_path_str = self.pmdg_77er_path_var.get(); path_label_for_error = "777-200ER Path"
                elif selected_variant == "777-300ER": required_base_pkg_path_str = self.pmdg_77w_path_var.get(); path_label_for_error = "777-300ER Path"
                elif selected_variant == "777F": required_base_pkg_path_str = self.pmdg_77f_path_var.get(); path_label_for_error = "777F Path"
            elif selected_variant.startswith("737"):
                if "600" in selected_variant: required_base_pkg_path_str = self.pmdg_736_path_var.get(); path_label_for_error = "737-600 Path"
                elif "700" in selected_variant: required_base_pkg_path_str = self.pmdg_737_path_var.get(); path_label_for_error = "737-700 (Base) Path"
                elif "800" in selected_variant: required_base_pkg_path_str = self.pmdg_738_path_var.get(); path_label_for_error = "737-800 (Base) Path"
                elif "900" in selected_variant: required_base_pkg_path_str = self.pmdg_739_path_var.get(); path_label_for_error = "737-900 (Base) Path"
            
            if not required_base_pkg_path_str:
                errors.append(f"- The '{path_label_for_error}' in Setup tab is required for the selected '{selected_variant}' variant but is not set.")
            elif not Path(required_base_pkg_path_str).is_dir():
                 errors.append(f"- The '{path_label_for_error}' ('{required_base_pkg_path_str}') in Setup tab is not a valid directory.")


        if errors:
            error_message = "Please correct the following configuration issues before installing:\n\n" + "\n".join(errors)
            messagebox.showerror("Configuration Errors", error_message)
            if any("Community" in e or "Reference" in e or "LocalState" in e or "Package" in e or PTP_CONVERTER_EXE_NAME in e or "Path" in e or "Setup" in e for e in errors):
                self.notebook.select(0) 
            elif any("Variant" in e or "livery" in e for e in errors): # Errors related to install tab selections
                self.notebook.select(1) 
            return

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Starting installation...")
        self.log("Starting installation process...", "STEP")
        self.install_button.config(state=tk.DISABLED)
        files_to_install = list(self.selected_zip_files) 
        install_thread = threading.Thread(target=self.install_livery_logic, args=(files_to_install,), daemon=True)
        install_thread.start()

    def _extract_archive(self, archive_path: Path, temp_dir: Path):
        self.log(f"Extracting ZIP archive '{archive_path.name}' to {temp_dir}...", "INFO")
        if archive_path.suffix.lower() != ".zip":
                raise ValueError(f"Unsupported file type for _extract_archive: {archive_path.name}. Only .zip.")
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                MAX_PATH_COMPONENT_LEN = 240 
                for member_info in zip_ref.infolist():
                    member_path_str = member_info.filename
                    normalized_member_path = Path(member_path_str).as_posix() 
                    if normalized_member_path.startswith('/') or '/../' in normalized_member_path or normalized_member_path.endswith('/..') or ".." in normalized_member_path.split('/'):
                        raise ValueError(f"ZIP archive contains potentially unsafe path: {member_path_str}")
                    if len(member_path_str) > MAX_PATH_COMPONENT_LEN : 
                            self.log(f"Warning: Long path component in ZIP: '{member_path_str[:100]}...'", "WARNING")
                
                zip_ref.extractall(temp_dir)
            self.log(f"ZIP archive '{archive_path.name}' extracted successfully.", "SUCCESS")
        except zipfile.BadZipFile:
            raise ValueError(f"Invalid or corrupt ZIP archive: {archive_path.name}")
        except (OSError, OverflowError) as e_os: 
            if "path too long" in str(e_os).lower() or (hasattr(e_os, 'winerror') and e_os.winerror == 206):
                    raise RuntimeError(f"Failed to extract '{archive_path.name}': File path too long within ZIP - {e_os}")
            raise RuntimeError(f"OS error extracting ZIP archive '{archive_path.name}': {e_os}")
        except Exception as e:
            raise RuntimeError(f"Failed to extract ZIP archive '{archive_path.name}': {e}")

    def _run_ptp_converter(self, ptp_file_to_process: Path, ptp_output_target_base_dir: Path) -> tuple[bool, Path | None, str]:
        if not self.ptp_converter_exe or not os.path.exists(self.ptp_converter_exe):
            error_msg = f"Error: {PTP_CONVERTER_EXE_NAME} not found. Cannot process {ptp_file_to_process.name}."
            self.log(error_msg, "ERROR")
            return False, None, error_msg

        self.log(f"Processing PTP file '{ptp_file_to_process.name}' using {Path(self.ptp_converter_exe).name}...", "INFO")

        converter_exe_dir = Path(self.ptp_converter_exe).parent
        
        # Directorio final (staging) donde el script de Python quiere el contenido final.
        unique_final_content_folder_name = f"__ptp_staged_content_{ptp_file_to_process.stem}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        target_final_content_staging_dir = ptp_output_target_base_dir / unique_final_content_folder_name
        
        # Directorio temporal para la copia del PTP (ruta corta)
        temp_storage_for_ptp_copy_str = tempfile.mkdtemp(prefix="pmdg_ptp_input_")
        temp_storage_for_ptp_copy_path = Path(temp_storage_for_ptp_copy_str)
        
        temp_ptp_filename_for_processing = f"input_{datetime.now().strftime('%f')}.ptp"
        absolute_path_to_copied_ptp = temp_storage_for_ptp_copy_path / temp_ptp_filename_for_processing
        
        # ESTA ES LA UBICACIÓN CORRECTA DE LA SALIDA NATIVA DEL CONVERTIDOR:
        # En el mismo directorio que el PTP de entrada (copiado), con el stem del PTP de entrada.
        converter_native_output_dir = absolute_path_to_copied_ptp.parent / absolute_path_to_copied_ptp.stem
        
        final_error_msg = ""
        try:
            target_final_content_staging_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ptp_file_to_process, absolute_path_to_copied_ptp)
            self.log(f"Copied '{ptp_file_to_process.name}' to temp location '{absolute_path_to_copied_ptp}' for processing.", "DETAIL")

            if converter_native_output_dir.exists(): # Limpiar salida nativa anterior si existe
                shutil.rmtree(converter_native_output_dir)

            # Ejecutar ptp_converter.exe. CWD es el directorio del .exe, se pasa la ruta absoluta al PTP.
            self.log(f"Executing: \"{self.ptp_converter_exe}\" \"{str(absolute_path_to_copied_ptp)}\" (CWD: {str(converter_exe_dir)})", "CMD")
            process = subprocess.run(
                [self.ptp_converter_exe, str(absolute_path_to_copied_ptp)],
                capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore',
                cwd=str(converter_exe_dir) 
            )

            ptp_converter_stdout = process.stdout.strip() if process.stdout else ""
            ptp_converter_stderr = process.stderr.strip() if process.stderr else ""

            if ptp_converter_stdout: self.log(f"Output from {PTP_CONVERTER_EXE_NAME}:\n{ptp_converter_stdout}", "DETAIL")
            
            ptp_failed = False
            tool_error_detected = ""

            if process.returncode != 0:
                tool_error_detected = f"PTP Converter exit code {process.returncode}."
                ptp_failed = True
            
            # Verificar stdout en busca de errores conocidos, ya que ptp_converter.exe puede no usar códigos de salida correctamente.
            if ptp_converter_stdout:
                stdout_lower = ptp_converter_stdout.lower()
                # Comprobar si "done!" NO está, Y hay un error, podría ser más fiable
                if "error: system.applicationexception: cab extraction error" in stdout_lower or \
                   "invalid parameters passed to extraction function" in stdout_lower:
                    tool_error_detected = "PTP Converter: CAB extraction error (reported in stdout)."
                    ptp_failed = True
                elif "error:" in stdout_lower and "done!" not in stdout_lower and not tool_error_detected:
                    tool_error_detected = "PTP Converter: Generic error (reported in stdout)."
                    ptp_failed = True
            
            if ptp_converter_stderr:
                stderr_lower = ptp_converter_stderr.lower()
                if "error" in stderr_lower or "failed" in stderr_lower:
                    if not tool_error_detected: tool_error_detected = "PTP Converter error (reported in stderr)."
                    ptp_failed = True
                if ptp_converter_stderr: # Loguear siempre si hay algo en stderr
                    self.log(f"Stderr from {PTP_CONVERTER_EXE_NAME}:\n{ptp_converter_stderr}", 
                             "ERROR" if (ptp_failed and ("error" in stderr_lower or "failed" in stderr_lower)) else "WARNING")

            # Después de que la herramienta se ejecute, verificar la carpeta de salida nativa ESPERADA
            if not ptp_failed:
                if not converter_native_output_dir.is_dir(): # AQUÍ ESTÁ LA VERIFICACIÓN CLAVE
                    tool_error_detected = f"PTP Converter output folder '{converter_native_output_dir.name}' not created at expected location '{converter_native_output_dir}'."
                    ptp_failed = True
                elif not any(converter_native_output_dir.iterdir()):
                    if "done!" not in ptp_converter_stdout.lower(): # Si dijo DONE pero está vacía, es raro pero no un error per se para esta comprobación
                        tool_error_detected = f"PTP Converter output folder '{converter_native_output_dir.name}' is empty and tool did not report DONE."
                        ptp_failed = True
                    else:
                         self.log(f"PTP Converter output folder '{converter_native_output_dir.name}' is empty, but tool reported DONE.", "DETAIL")
            
            if ptp_failed:
                final_error_msg = f"PTP conversion FAILED for '{ptp_file_to_process.name}'. Detail: {tool_error_detected or 'Reason unknown from PTP tool output.'}"
                self.log(final_error_msg, "ERROR")
                return False, None, final_error_msg
            
            # Mover contenido desde converter_native_output_dir a target_final_content_staging_dir
            self.log(f"Moving extracted content from '{converter_native_output_dir}' to final staging '{target_final_content_staging_dir}'", "DETAIL")
            moved_count = 0
            if converter_native_output_dir.exists() and any(converter_native_output_dir.iterdir()):
                for item_name in os.listdir(converter_native_output_dir):
                    source_item = converter_native_output_dir / item_name
                    destination_item = target_final_content_staging_dir / item_name
                    try:
                        shutil.move(str(source_item), str(destination_item))
                        moved_count += 1
                    except Exception as e_move_item:
                        error_moving = f"Failed to move item '{source_item.name}' from PTP native output: {e_move_item}"
                        self.log(error_moving, "ERROR")
                        return False, None, error_moving 
            
                if moved_count == 0 and any(converter_native_output_dir.iterdir()):
                    error_no_move = f"No files were moved from PTP native output '{converter_native_output_dir}', but it was not empty."
                    self.log(error_no_move, "WARNING")
                    return False, None, error_no_move
            else:
                # Esto es normal si el PTP original estaba vacío y `ptp_converter.exe` lo manejó creando una carpeta vacía y dijo "DONE!"
                self.log(f"PTP native output directory '{converter_native_output_dir}' is empty or does not exist, but tool reported success. Assuming empty PTP or already processed content.", "DETAIL")


            self.log(f"PTP file '{ptp_file_to_process.name}' processed. Content staged in: {target_final_content_staging_dir}", "SUCCESS")
            return True, target_final_content_staging_dir, ""

        except Exception as e:
            final_error_msg = f"CRITICAL error during _run_ptp_converter for '{ptp_file_to_process.name}': {e}"
            self.log(final_error_msg, "ERROR")
            import traceback
            self.log(f"PTP Converter Exception Traceback: {traceback.format_exc()}", "DETAIL")
            return False, None, final_error_msg
        finally:
            # Limpiar el directorio temporal donde se copió el PTP (esto también eliminará converter_native_output_dir si está dentro)
            if temp_storage_for_ptp_copy_path.exists():
                try:
                    shutil.rmtree(temp_storage_for_ptp_copy_path)
                    self.log(f"Cleaned up temp storage for PTP copy: {temp_storage_for_ptp_copy_path}", "DETAIL")
                except Exception as e_clean_storage:
                    self.log(f"Warning: Could not clean up temp storage '{temp_storage_for_ptp_copy_path}': {e_clean_storage}", "WARNING")
            # La carpeta converter_native_output_in_exe_dir (si se creó en el dir del exe) ya no es el objetivo principal de salida.+

        """
        Procesa un archivo PTP. CWD se establece en el directorio del ptp_converter.exe.
        El PTP se copia a una ruta temporal corta y se pasa como ruta absoluta.
        Retorna: (éxito, ruta_al_contenido_final_procesado_del_ptp | None, mensaje_de_error_str)
        """
        if not self.ptp_converter_exe or not os.path.exists(self.ptp_converter_exe):
            error_msg = f"Error: {PTP_CONVERTER_EXE_NAME} not found. Cannot process {ptp_file_to_process.name}."
            self.log(error_msg, "ERROR")
            return False, None, error_msg

        self.log(f"Processing PTP file '{ptp_file_to_process.name}' using {Path(self.ptp_converter_exe).name}...", "INFO")

        converter_exe_dir = Path(self.ptp_converter_exe).parent
        unique_final_content_folder_name = f"__ptp_staged_content_{ptp_file_to_process.stem}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        target_final_content_staging_dir = ptp_output_target_base_dir / unique_final_content_folder_name
        
        # Directorio temporal para la copia del PTP (ruta corta)
        temp_storage_for_ptp_copy_str = tempfile.mkdtemp(prefix="pmdg_ptp_input_")
        temp_storage_for_ptp_copy_path = Path(temp_storage_for_ptp_copy_str)
        
        # Nombre temporal sin espacios para el archivo PTP copiado
        temp_ptp_filename_for_processing = f"input_{datetime.now().strftime('%f')}.ptp"
        absolute_path_to_copied_ptp = temp_storage_for_ptp_copy_path / temp_ptp_filename_for_processing
        
        # El convertidor, si CWD es su propio directorio, creará la carpeta de salida allí.
        # Ej: _MEIxxxx/input_123456 (donde input_123456 es el stem del PTP temporal)
        temp_ptp_stem_for_processing = absolute_path_to_copied_ptp.stem 
        converter_native_output_in_exe_dir = converter_exe_dir / temp_ptp_stem_for_processing
        
        final_error_msg = ""

        try:
            target_final_content_staging_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ptp_file_to_process, absolute_path_to_copied_ptp)
            self.log(f"Copied '{ptp_file_to_process.name}' to temp location '{absolute_path_to_copied_ptp}' for processing.", "DETAIL")

            if converter_native_output_in_exe_dir.exists(): # Limpiar salida nativa anterior si existe
                shutil.rmtree(converter_native_output_in_exe_dir)

            self.log(f"Executing: \"{self.ptp_converter_exe}\" \"{str(absolute_path_to_copied_ptp)}\" (CWD: {str(converter_exe_dir)})", "CMD")
            process = subprocess.run(
                [self.ptp_converter_exe, str(absolute_path_to_copied_ptp)], # Ruta absoluta al PTP copiado
                capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore',
                cwd=str(converter_exe_dir) # Establecer CWD al directorio del ejecutable
            )

            ptp_converter_stdout = process.stdout.strip() if process.stdout else ""
            ptp_converter_stderr = process.stderr.strip() if process.stderr else ""

            if ptp_converter_stdout: self.log(f"Output from {PTP_CONVERTER_EXE_NAME}:\n{ptp_converter_stdout}", "DETAIL")
            
            ptp_failed = False
            tool_error_detected = ""

            if process.returncode != 0:
                tool_error_detected = f"PTP Converter exit code {process.returncode}."
                ptp_failed = True
            
            if ptp_converter_stdout:
                stdout_lower = ptp_converter_stdout.lower()
                if "error: system.applicationexception: cab extraction error" in stdout_lower or \
                   "invalid parameters passed to extraction function" in stdout_lower:
                    tool_error_detected = "PTP Converter: CAB extraction error (stdout)."
                    ptp_failed = True
                elif "error:" in stdout_lower and not tool_error_detected :
                    tool_error_detected = "PTP Converter: Generic error (stdout)."
                    ptp_failed = True

            if ptp_converter_stderr:
                stderr_lower = ptp_converter_stderr.lower()
                if "error" in stderr_lower or "failed" in stderr_lower:
                    if not tool_error_detected: tool_error_detected = "PTP Converter error (stderr)."
                    ptp_failed = True
                self.log(f"Stderr from {PTP_CONVERTER_EXE_NAME}:\n{ptp_converter_stderr}", 
                         "ERROR" if tool_error_detected and "error" in stderr_lower else "WARNING") # Log con más contexto

            # Después de que la herramienta se ejecute (o falle), verificar la carpeta de salida nativa
            if not ptp_failed:
                if not converter_native_output_in_exe_dir.is_dir():
                    tool_error_detected = f"PTP Converter output folder '{converter_native_output_in_exe_dir.name}' not created in its CWD."
                    ptp_failed = True
                elif not any(converter_native_output_in_exe_dir.iterdir()):
                    tool_error_detected = f"PTP Converter output folder '{converter_native_output_in_exe_dir.name}' is empty."
                    ptp_failed = True
            
            if ptp_failed:
                final_error_msg = f"PTP conversion FAILED for '{ptp_file_to_process.name}'. Detail: {tool_error_detected or 'Reason unknown from PTP tool output.'}"
                self.log(final_error_msg, "ERROR")
                return False, None, final_error_msg
            
            # Mover contenido desde la salida nativa del convertidor (en converter_exe_dir) a target_final_content_staging_dir
            self.log(f"Moving extracted PTP content from '{converter_native_output_in_exe_dir}' to final staging '{target_final_content_staging_dir}'", "DETAIL")
            moved_count = 0
            for item_name in os.listdir(converter_native_output_in_exe_dir):
                source_item = converter_native_output_in_exe_dir / item_name
                destination_item = target_final_content_staging_dir / item_name
                try:
                    shutil.move(str(source_item), str(destination_item))
                    moved_count += 1
                except Exception as e_move_item:
                    error_moving = f"Failed to move item '{source_item.name}' from PTP native output: {e_move_item}"
                    self.log(error_moving, "ERROR")
                    # Si un ítem no se puede mover, es un fallo crítico para este PTP
                    return False, None, error_moving
            
            if moved_count == 0 and any(converter_native_output_in_exe_dir.iterdir()):
                error_no_move = f"No files were moved from PTP native output '{converter_native_output_in_exe_dir}', but it was not empty."
                self.log(error_no_move, "WARNING")
                return False, None, error_no_move

            self.log(f"PTP file '{ptp_file_to_process.name}' processed. Content staged in: {target_final_content_staging_dir}", "SUCCESS")
            return True, target_final_content_staging_dir, ""

        except Exception as e:
            final_error_msg = f"CRITICAL error during _run_ptp_converter for '{ptp_file_to_process.name}': {e}"
            self.log(final_error_msg, "ERROR")
            import traceback
            self.log(f"PTP Converter Exception Traceback: {traceback.format_exc()}", "DETAIL")
            return False, None, final_error_msg
        finally:
            # Limpiar el directorio temporal donde se copió el PTP
            if temp_storage_for_ptp_copy_path.exists():
                try:
                    shutil.rmtree(temp_storage_for_ptp_copy_path)
                    self.log(f"Cleaned up temp storage for PTP copy: {temp_storage_for_ptp_copy_path}", "DETAIL")
                except Exception as e_clean_storage:
                    self.log(f"Warning: Could not clean up temp storage '{temp_storage_for_ptp_copy_path}': {e_clean_storage}", "WARNING")
            
            # Limpiar la carpeta de salida nativa del convertidor SI AÚN EXISTE Y ESTÁ VACÍA
            # (si los archivos se movieron correctamente, debería estar vacía o no existir)
            if converter_native_output_in_exe_dir.exists():
                try:
                    if not any(converter_native_output_in_exe_dir.iterdir()): # Solo si está vacía
                        converter_native_output_in_exe_dir.rmdir()
                        self.log(f"Cleaned up empty native output dir in converter's CWD: {converter_native_output_in_exe_dir}", "DETAIL")
                except Exception as e_clean_native:
                    self.log(f"Warning: Could not remove converter native output dir '{converter_native_output_in_exe_dir}': {e_clean_native}", "WARNING")

    def _reorganize_ptp_output(self, ptp_content_folder: Path) -> tuple[bool, str]:
        self.log(f"Reorganizing extracted PTP content from: {ptp_content_folder}", "STEP")
        # This function standardizes the structure of a PTP-extracted livery
        # to match what a typical ZIP livery might look like (aircraft.cfg, model folder, texture folders at root).
        try:
            config_cfg_original_path = ptp_content_folder / "Config.cfg"
            aircraft_cfg_target_path = ptp_content_folder / "aircraft.cfg"
            original_cfg_lines = []

            if config_cfg_original_path.is_file():
                self.log(f"Reading PTP's '{config_cfg_original_path.name}' for aircraft.cfg conversion.", "DETAIL")
                with open(config_cfg_original_path, 'r', encoding='utf-8', errors='ignore') as f:
                    original_cfg_lines = f.readlines()
            elif aircraft_cfg_target_path.is_file():
                self.log(f"'{aircraft_cfg_target_path.name}' already exists in PTP output. Using as base.", "DETAIL")
                with open(aircraft_cfg_target_path, 'r', encoding='utf-8', errors='ignore') as f:
                    original_cfg_lines = f.readlines()
            else:
                return False, f"PTP Error: Neither Config.cfg nor aircraft.cfg found in '{ptp_content_folder}'."

            if not original_cfg_lines:
                return False, "PTP Error: Configuration file (Config.cfg or aircraft.cfg) is empty."

            model_value_in_ptp_cfg = ""
            for line in original_cfg_lines:
                if line.strip().lower().startswith("model="):
                    model_value_in_ptp_cfg = line.split('=', 1)[1].strip().strip('"')
                    self.log(f"Found 'model={model_value_in_ptp_cfg}' in PTP config.", "DETAIL")
                    break
            
            # Handle model.cfg: PMDG PTPs often have model.cfg at the root.
            # Standard liveries expect it inside a "model" or "model.XXX" folder.
            ptp_model_cfg_path = ptp_content_folder / "model.cfg"
            if ptp_model_cfg_path.is_file():
                model_folder_name = "model"
                if model_value_in_ptp_cfg: # If Config.cfg specified model=XXX, use model.XXX
                    model_folder_name = f"model.{model_value_in_ptp_cfg}"
                
                target_model_dir = ptp_content_folder / model_folder_name
                target_model_dir.mkdir(exist_ok=True)
                final_model_cfg_path = target_model_dir / "model.cfg"
                
                self.log(f"Moving PTP's root 'model.cfg' to '{final_model_cfg_path}'.", "DETAIL")
                shutil.move(str(ptp_model_cfg_path), str(final_model_cfg_path))

            # Prepare aircraft.cfg content (from Config.cfg if it existed)
            new_aircraft_cfg_lines = []
            fltsim0_header_found = False
            for line in original_cfg_lines:
                stripped_line_lower = line.strip().lower()
                if stripped_line_lower.startswith("[fltsim."): # Normalize to [fltsim.0]
                    eol = '\r\n' if line.endswith('\r\n') else '\n'
                    new_aircraft_cfg_lines.append(f"[fltsim.0]{eol}")
                    if stripped_line_lower != "[fltsim.0]":
                         self.log(f"Normalized PTP config header '{line.strip()}' to '[fltsim.0]'.", "DETAIL")
                    fltsim0_header_found = True
                else:
                    new_aircraft_cfg_lines.append(line)
            
            if not fltsim0_header_found and new_aircraft_cfg_lines: # If no [fltsim.X] but content exists
                self.log("Warning: No [fltsim.X] section found in PTP config. Prepending [fltsim.0]. Livery might need manual check.", "WARNING")
                eol = '\r\n' if new_aircraft_cfg_lines[0].endswith('\r\n') else '\n'
                new_aircraft_cfg_lines.insert(0, f"[fltsim.0]{eol}")


            # Ensure [VERSION] section
            final_cfg_str = "".join(new_aircraft_cfg_lines)
            if not final_cfg_str.lstrip().lower().startswith("[version]"):
                final_cfg_str = "[VERSION]\nmajor=1\nminor=0\n\n" + final_cfg_str
                self.log("Prepended [VERSION] section to the aircraft.cfg from PTP.", "DETAIL")

            with open(aircraft_cfg_target_path, 'w', encoding='utf-8', newline='') as f:
                f.write(final_cfg_str)
            self.log(f"Final 'aircraft.cfg' created/updated in PTP staging area: {aircraft_cfg_target_path}", "SUCCESS")

            if config_cfg_original_path.is_file() and config_cfg_original_path != aircraft_cfg_target_path :
                try: config_cfg_original_path.unlink(); self.log(f"Deleted original PTP '{config_cfg_original_path.name}'.", "DETAIL")
                except OSError as e: self.log(f"Could not delete PTP '{config_cfg_original_path.name}': {e}", "WARNING")
            
            # Handle Aircraft.ini -> options.ini (for consistency with ZIPs)
            ptp_aircraft_ini = ptp_content_folder / "Aircraft.ini"
            target_options_ini = ptp_content_folder / "options.ini"
            if ptp_aircraft_ini.is_file():
                if target_options_ini.exists():
                    self.log(f"Warning: Both '{ptp_aircraft_ini.name}' and '{target_options_ini.name}' exist in PTP output. Overwriting options.ini.", "WARNING")
                    target_options_ini.unlink()
                ptp_aircraft_ini.rename(target_options_ini)
                self.log(f"Renamed PTP's '{ptp_aircraft_ini.name}' to '{target_options_ini.name}'.", "DETAIL")
            
            # Delete other PTP-specific files not needed for standard livery structure
            files_to_delete_from_ptp = ["Settings.dat", " Manifest.ini", "Product.ini"] # Note leading space in Manifest.ini sometimes
            for f_name in files_to_delete_from_ptp:
                file_path = ptp_content_folder / f_name.strip() # Use strip for safety
                if file_path.is_file():
                    try: file_path.unlink(); self.log(f"Deleted PTP-specific file: '{file_path.name}'", "DETAIL")
                    except OSError as e: self.log(f"Could not delete PTP file '{file_path.name}': {e}", "WARNING")
            
            self.log("PTP output reorganization successful.", "SUCCESS")
            return True, ""
        except Exception as e:
            self.log(f"Error during PTP output reorganization for '{ptp_content_folder}': {e}", "ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "DETAIL")
            return False, str(e)

    def _is_nested_archive(self, directory: Path) -> bool:
        # (Implementation from previous response, seems okay, ensure __temp_ checks are robust)
        zip_count = 0; ptp_count = 0; other_file_folder_count = 0
        has_texture_folder = False; has_aircraft_cfg = False
        check_dir = directory
        try:
            items = list(check_dir.iterdir())
            if len(items) == 1 and items[0].is_dir() and not items[0].name.startswith(('.', '__MACOSX', '__temp_')):
                check_dir = items[0]
            
            for item in check_dir.iterdir():
                if item.name.startswith(('.', '__MACOSX', '__temp_')): continue
                if item.is_file():
                    if item.suffix.lower() == '.zip': zip_count += 1
                    elif item.suffix.lower() == '.ptp': ptp_count += 1
                    elif item.name.lower() == 'aircraft.cfg': has_aircraft_cfg = True; other_file_folder_count +=1
                    else: other_file_folder_count += 1
                elif item.is_dir():
                    other_file_folder_count += 1
                    if item.name.lower().startswith('texture.'): has_texture_folder = True
        except OSError as e:
            self.log(f"Error checking for nested archives in '{check_dir}': {e}", "WARNING"); return False
        
        archive_file_count = zip_count + ptp_count
        if has_texture_folder or has_aircraft_cfg: is_nested = False
        elif archive_file_count > 0 and other_file_folder_count <= 2 : is_nested = True
        elif archive_file_count > 0 : is_nested = True
        else: is_nested = False

        if is_nested: self.log(f"Nested archive detected in '{check_dir.name}'.", "INFO")
        return is_nested
    
    def _process_single_livery(self,
                               extracted_livery_source_path: Path,
                               original_archive_path: Path, # This is the path to the .zip or .ptp file being processed (or sub-PTP)
                               common_config: dict,
                               specific_livery_name: str | None = None # Name from PTP settings for sub-liveries
                               ) -> tuple[bool, str]:
        """
        Processes a single prepared livery from 'extracted_livery_source_path'.
        Copies files to the final destination, modifies aircraft.cfg, handles .ini.
        'extracted_livery_source_path' is the root of the prepared livery content.
        'common_config' holds paths and aircraft variant info.
        'specific_livery_name' is used for sub-liveries from multi-PTPs, overriding other name detection.
        """
        livery_success = False
        processing_error_detail = "Unknown error during individual livery processing."
        livery_display_name = "Unknown Livery" # Default
        final_livery_dest_path: Path | None = None

        try:
            # --- Determine the livery display name ---
            if specific_livery_name:
                livery_display_name = specific_livery_name
                # original_archive_path.name here would be like "Texture.1.PTP" or the nested ZIP name
                self.log(f"Using specific name: '{livery_display_name}' (from PTP settings/nested archive for content of '{original_archive_path.name}')", "INFO")
            # Check if this is the single, top-level archive selected by the user AND a custom name is provided in the UI
            elif len(self.selected_zip_files) == 1 and Path(self.selected_zip_files[0]) == original_archive_path and self.custom_name_var.get():
                livery_display_name = self.custom_name_var.get()
                self.log(f"Using user-provided custom name: '{livery_display_name}' for the single selected archive: {original_archive_path.name}", "INFO")
            else:
                # Fallback for:
                # - Multiple top-level archives selected by the user.
                # - A single top-level archive selected, but no custom name provided.
                # - Nested ZIP archives (that are not sub-PTPs handled by specific_livery_name).
                livery_display_name = self.get_livery_name(original_archive_path, extracted_livery_source_path)
                self.log(f"Auto-detected/generated name: '{livery_display_name}' for {original_archive_path.name}", "INFO")

            sanitized_fs_foldername_suffix = re.sub(r'[\\/*?:"<>|]', '_', livery_display_name).strip().replace('.', '_')
            if not sanitized_fs_foldername_suffix:
                sanitized_fs_foldername_suffix = f"UnnamedLivery_{original_archive_path.stem}_{datetime.now().strftime('%S%f')}"
                self.log(f"Sanitized livery name was empty, using generated folder suffix: '{sanitized_fs_foldername_suffix}'.", "WARNING")

            # Construct the final destination path for this specific livery
            final_livery_folder_name_in_simobjects = f"{common_config['base_aircraft_folder_name']} {sanitized_fs_foldername_suffix}"
            final_livery_dest_path = common_config['main_package_folder'] / "SimObjects" / "Airplanes" / final_livery_folder_name_in_simobjects
            
            self.log(f"Final livery destination folder: {final_livery_dest_path}", "DETAIL")

            if final_livery_dest_path.exists():
                self.log(f"Destination folder '{final_livery_dest_path.name}' already exists. Overwriting...", "WARNING")
                try:
                    shutil.rmtree(final_livery_dest_path)
                    self.log(f"Existing destination folder deleted.", "DETAIL")
                    time.sleep(0.1) # Brief pause to allow filesystem to catch up
                except OSError as e:
                    raise RuntimeError(f"Failed to delete existing livery folder '{final_livery_dest_path}': {e}. Check if MSFS or File Explorer is using it.")
            
            final_livery_dest_path.mkdir(parents=True, exist_ok=True)
            self.log(f"Final livery destination folder created: {final_livery_dest_path.name}", "SUCCESS")

            self.log(f"Copying files from prepared source: {extracted_livery_source_path} to {final_livery_dest_path.name}", "INFO")

            # --- Locate and copy aircraft.cfg ---
            aircraft_cfg_source_str = self.find_file_in_dir(extracted_livery_source_path, "aircraft.cfg")
            if not aircraft_cfg_source_str or not Path(aircraft_cfg_source_str).is_file():
                # Check one level deeper, common in simple zips: LiveryName/aircraft.cfg
                if extracted_livery_source_path.is_dir():
                    for item in extracted_livery_source_path.iterdir():
                        if item.is_dir() and not item.name.startswith(('.', '__MACOSX', '__temp_')): # Avoid special/temp folders
                            cfg_in_sub = self.find_file_in_dir(item, "aircraft.cfg")
                            if cfg_in_sub:
                                aircraft_cfg_source_str = cfg_in_sub
                                self.log(f"Found aircraft.cfg in subfolder: {item.name}", "DETAIL")
                                break
                if not aircraft_cfg_source_str:            
                    raise FileNotFoundError(f"aircraft.cfg not found in processed source '{extracted_livery_source_path}' or its direct subfolders.")
            
            aircraft_cfg_source_path = Path(aircraft_cfg_source_str)
            aircraft_cfg_final_target_path = final_livery_dest_path / "aircraft.cfg"
            shutil.copy2(aircraft_cfg_source_path, aircraft_cfg_final_target_path)
            self.log(f"Copied '{aircraft_cfg_source_path.name}' to '{aircraft_cfg_final_target_path}'.", "DETAIL")
            
            # The directory containing the aircraft.cfg is considered the root of the livery content
            effective_content_source_dir = aircraft_cfg_source_path.parent

            # --- Copy model folder(s) ---
            model_folder_copied = False
            for item in effective_content_source_dir.iterdir():
                if item.is_dir() and item.name.lower().startswith("model"):
                    model_src_path = item
                    model_dest_path = final_livery_dest_path / model_src_path.name # Preserve original model folder name (e.g., model.XXX)
                    self.log(f"Copying model folder '{model_src_path.name}' to '{model_dest_path}'...", "DETAIL")
                    shutil.copytree(model_src_path, model_dest_path, dirs_exist_ok=True)
                    model_folder_copied = True 
            if not model_folder_copied:
                self.log("No 'model.*' folder found in source. This is okay if model is shared or defined differently.", "DETAIL")

            # --- Copy texture folder(s) ---
            texture_dirs_source_str_list = self.find_texture_dirs_in_dir(effective_content_source_dir)
            if not texture_dirs_source_str_list:
                self.log(f"Warning: No 'texture.*' folders found in processed source content directory '{effective_content_source_dir}'. Livery may not appear correctly.", "WARNING")
            else:
                for tex_dir_src_str in texture_dirs_source_str_list:
                    tex_dir_src_path = Path(tex_dir_src_str)
                    tex_dir_dest_path = final_livery_dest_path / tex_dir_src_path.name # Preserve original texture folder name
                    shutil.copytree(tex_dir_src_path, tex_dir_dest_path, dirs_exist_ok=True)
                    self.log(f"Copied texture folder '{tex_dir_src_path.name}' to '{tex_dir_dest_path}'.", "DETAIL")
            
            # --- Copy other relevant files (e.g. panel.cfg, sound.cfg if they exist at the same level as aircraft.cfg) ---
            copied_extras_count = 0
            atc_id_for_ini_handling = self.extract_atc_id(aircraft_cfg_final_target_path) # Get ATC ID from the *copied* aircraft.cfg
            
            # Define files that are typically handled separately or are part of the core structure already copied
            files_to_exclude_lc = {"aircraft.cfg", "options.ini", "layout.json", "manifest.json", 
                                   "config.cfg", "aircraft.ini", "settings.dat", "model.cfg"} # PTP specific files
            if atc_id_for_ini_handling: # If an ATC ID was found, also exclude its potential .ini name
                files_to_exclude_lc.add(f"{atc_id_for_ini_handling}.ini".lower())

            for item_name in os.listdir(effective_content_source_dir):
                item_src_full_path = effective_content_source_dir / item_name
                
                # Skip already processed/irrelevant directories and specific files
                if item_src_full_path.is_dir() and (item_name.lower().startswith("model") or item_name.lower().startswith("texture.")):
                    continue 
                if item_src_full_path.is_file() and item_name.lower() in files_to_exclude_lc:
                    continue 
                
                if item_src_full_path.is_file():
                    # Copy common config/data/font files if present.
                    common_extensions = ['.cfg', '.xml', '.dat', '.txt', '.flags', '.ttf', '.otf', '.ini', '.sound', '.air', '.flt', '.fdm']
                    # Check if it's not one of the already excluded .ini files by name
                    is_potentially_options_ini = item_name.lower() == "options.ini"
                    is_potentially_atc_id_ini = atc_id_for_ini_handling and item_name.lower() == f"{atc_id_for_ini_handling}.ini"

                    if item_src_full_path.suffix.lower() in common_extensions and not is_potentially_options_ini and not is_potentially_atc_id_ini:
                        item_dest_full_path = final_livery_dest_path / item_name
                        try:
                            shutil.copy2(item_src_full_path, item_dest_full_path)
                            self.log(f"Copied extra file '{item_name}' to '{final_livery_dest_path.name}'.", "DETAIL")
                            copied_extras_count += 1
                        except Exception as e_copy_ex:
                            self.log(f"Could not copy extra file '{item_name}': {e_copy_ex}", "WARNING")
            if copied_extras_count > 0: self.log(f"Copied {copied_extras_count} additional relevant file(s).", "DETAIL")
            self.log("Essential livery file copying complete.", "SUCCESS")

            # --- Process .ini file for LocalState ---
            self.log("Processing .ini file for LocalState...", "INFO")
            source_ini_to_copy_path: Path | None = None
            target_ini_name_in_localstate: str | None = None
            ini_file_found_in_source = False
            ini_copied_to_localstate = False

            if atc_id_for_ini_handling: # ATC ID must be known to name the .ini file correctly
                target_ini_name_in_localstate = f"{atc_id_for_ini_handling}.ini"
                
                # Prefer "options.ini" if present in the source livery structure
                options_ini_in_source_str = self.find_file_in_dir(effective_content_source_dir, "options.ini")
                if options_ini_in_source_str and Path(options_ini_in_source_str).is_file():
                    source_ini_to_copy_path = Path(options_ini_in_source_str)
                    ini_file_found_in_source = True
                    self.log(f"Found '{source_ini_to_copy_path.name}' in source.", "DETAIL")
                else: 
                    # If no "options.ini", check if an .ini file already named with ATC_ID exists
                    atc_id_ini_in_source_str = self.find_file_in_dir(effective_content_source_dir, target_ini_name_in_localstate.lower())
                    if atc_id_ini_in_source_str and Path(atc_id_ini_in_source_str).is_file():
                        source_ini_to_copy_path = Path(atc_id_ini_in_source_str)
                        ini_file_found_in_source = True
                        self.log(f"Found pre-named '{source_ini_to_copy_path.name}' in source.", "DETAIL")
            
            if ini_file_found_in_source and source_ini_to_copy_path and target_ini_name_in_localstate:
                pmdg_ls_pkg_path = common_config['pmdg_localstate_package_path'] # Path to pmdg-aircraft-737, etc. in LocalState
                if pmdg_ls_pkg_path.is_dir():
                    target_ini_storage_dir = pmdg_ls_pkg_path / "work" / "Aircraft"
                    target_ini_final_path_in_localstate = target_ini_storage_dir / target_ini_name_in_localstate
                    try:
                        target_ini_storage_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_ini_to_copy_path, target_ini_final_path_in_localstate)
                        self.log(f"INI file '{source_ini_to_copy_path.name}' copied as '{target_ini_name_in_localstate}' to: {target_ini_storage_dir}", "SUCCESS")
                        ini_copied_to_localstate = True
                    except Exception as e_cp_ini:
                        self.log(f"Failed to copy INI '{source_ini_to_copy_path.name}' to '{target_ini_final_path_in_localstate}': {e_cp_ini}", "ERROR")
                else:
                    self.log(f"PMDG LocalState Package Path for '{common_config['aircraft_variant']}' is invalid: {pmdg_ls_pkg_path}. Cannot copy INI.", "ERROR")
            elif atc_id_for_ini_handling: # An ATC ID was found, but no suitable .ini file
                self.log(f"Neither 'options.ini' nor '{atc_id_for_ini_handling}.ini' found in source '{effective_content_source_dir}'. No INI copied to LocalState.", "DETAIL")
            else: # No ATC ID found in aircraft.cfg
                self.log("ATC ID not found in aircraft.cfg; cannot process .ini for LocalState.", "WARNING")

            # --- Modify aircraft.cfg in the final destination ---
            self.log(f"Modifying aircraft.cfg at: {aircraft_cfg_final_target_path}...", "INFO")
            self.modify_aircraft_cfg(aircraft_cfg_final_target_path, 
                                     common_config['aircraft_variant'], 
                                     livery_display_name) # Pass the determined livery_display_name

            livery_success = True
            processing_error_detail = f"Installed successfully as '{livery_display_name}'."
            if ini_file_found_in_source and not ini_copied_to_localstate and atc_id_for_ini_handling:
                ini_name_msg = source_ini_to_copy_path.name if source_ini_to_copy_path else "INI file"
                processing_error_detail += f" (Warning: {ini_name_msg} found but failed to copy to LocalState)"

        except (FileNotFoundError, ValueError, RuntimeError, OSError) as e_proc:
            processing_error_detail = str(e_proc)
            # Log the name that was being processed when the error occurred
            current_name_for_log = specific_livery_name or livery_display_name or original_archive_path.name
            self.log(f"LIVERY PROCESSING FAILED ({current_name_for_log}): {processing_error_detail}", "ERROR")
        except Exception as e_unexp: 
            current_name_for_log = specific_livery_name or livery_display_name or original_archive_path.name
            processing_error_detail = f"Unexpected error processing livery {current_name_for_log}: {str(e_unexp)}"
            self.log(f"FATAL LIVERY ERROR ({current_name_for_log}): {processing_error_detail}", "ERROR")
            import traceback 
            self.log(f"Traceback _process_single_livery: {traceback.format_exc()}", "DETAIL")
        
        # --- Cleanup on failure ---
        if not livery_success and final_livery_dest_path and final_livery_dest_path.exists():
            self.log(f"Cleaning up failed livery folder: {final_livery_dest_path}", "WARNING")
            try:
                shutil.rmtree(final_livery_dest_path)
                self.log(f"Destination folder of failed livery removed: {final_livery_dest_path.name}", "INFO")
            except Exception as e_cleanup:
                self.log(f"Error removing failed livery folder '{final_livery_dest_path.name}': {e_cleanup}", "ERROR")
        
        return livery_success, processing_error_detail

    def _process_extracted_ptp_content(self,
                                       initial_ptp_extract_path: Path, 
                                       original_top_level_ptp_path: Path,
                                       common_config: dict,
                                       results_summary_list: list[dict],
                                       batch_success_counter: list[int], 
                                       batch_failure_flag_for_archive: list[bool]
                                       ) -> None:
        self.log(f"Examining PTP content from '{original_top_level_ptp_path.name}' in: {initial_ptp_extract_path}", "DETAIL")
        settings_dat_path = initial_ptp_extract_path / "Settings.dat"
        is_multi_livery_ptp = False
        sub_livery_ptp_files_info = [] 

        # Variables to store info about the first successfully processed sub-livery (potential texture base)
        # These are for the *currently processing top-level PTP pack*
        pack_base_livery_simobjects_folder_name: str | None = None
        pack_base_livery_texture_folder_name: str | None = None # e.g., "Texture.N203JE"
        pack_base_livery_texture_folder_path: Path | None = None # Full path to the installed texture folder of the base

        if settings_dat_path.is_file():
            self.log(f"Found Settings.dat: {settings_dat_path}", "INFO")
            parser = configparser.ConfigParser(interpolation=None, strict=False, allow_no_value=True)
            try:
                settings_content = settings_dat_path.read_text(encoding='utf-8', errors='ignore')
                if not settings_content.strip().startswith("["):
                    self.log("Settings.dat doesn't start with a section, prepending [Settings] for parser.", "DETAIL")
                    settings_content = "[Settings]\n" + settings_content
                
                parser.read_string(settings_content)

                if parser.has_section("Settings") and parser.has_option("Settings", "Type"):
                    ptp_type = parser.get("Settings", "Type", fallback="").strip().lower()
                    if ptp_type == "multi livery":
                        is_multi_livery_ptp = True
                        count = parser.getint("Settings", "Count", fallback=0)
                        self.log(f"Detected 'Multi Livery' PTP ('{original_top_level_ptp_path.name}') with {count} sub-liveries.", "INFO")
                        for i in range(1, count + 1):
                            section_name = f"Livery {i}"
                            if parser.has_section(section_name) and parser.has_option(section_name, "Filename"):
                                filename = parser.get(section_name, "Filename")
                                name_from_settings = parser.get(section_name, "Name", fallback=filename) 
                                sub_livery_ptp_files_info.append((filename, name_from_settings))
                            else:
                                self.log(f"Warning: Section '{section_name}' missing or 'Filename' option not found in Settings.dat for '{original_top_level_ptp_path.name}'.", "WARNING")
                                batch_failure_flag_for_archive[0] = True 
                                if not any(r["file"] == original_top_level_ptp_path.name and "Settings.dat malformed" in r["detail"] for r in results_summary_list):
                                     results_summary_list.append({ "file": original_top_level_ptp_path.name, "success": False, "detail": f"Settings.dat malformed (section {section_name})."})
                    # ... (rest of Settings.dat parsing as before) ...
            except Exception as e_set:
                self.log(f"Error processing Settings.dat for '{original_top_level_ptp_path.name}': {e_set}. Assuming single PTP.", "WARNING")
                is_multi_livery_ptp = False # Force to single if parsing failed badly

        if is_multi_livery_ptp and sub_livery_ptp_files_info:
            self.log(f"Processing {len(sub_livery_ptp_files_info)} sub-liveries from '{original_top_level_ptp_path.name}'.", "INFO")
            for sub_livery_index, (ptp_filename_in_archive, livery_name_from_settings) in enumerate(sub_livery_ptp_files_info):
                sub_ptp_file_to_process = initial_ptp_extract_path / ptp_filename_in_archive
                display_name_for_log_and_summary = f"{original_top_level_ptp_path.name} -> {livery_name_from_settings} ({ptp_filename_in_archive})"

                if not sub_ptp_file_to_process.is_file():
                    self.log(f"Sub-PTP file '{ptp_filename_in_archive}' not found. Skipping.", "ERROR")
                    results_summary_list.append({"file": display_name_for_log_and_summary, "success": False, "detail": f"Sub-PTP file '{ptp_filename_in_archive}' not found."})
                    batch_failure_flag_for_archive[0] = True
                    continue

                self.log(f"--- Processing Sub-PTP: {display_name_for_log_and_summary} ---", "STEP")
                nested_temp_sub_ptp_processing_dir = initial_ptp_extract_path / f"__sub_ptp_proc_{sub_ptp_file_to_process.stem}_{datetime.now().strftime('%f')}"
                
                current_sub_livery_installed_texture_folder_path: Path | None = None
                original_cfg_for_eol_detection: list[str] | None = None # To help get_eol_char

                try:
                    nested_temp_sub_ptp_processing_dir.mkdir(parents=True, exist_ok=True)
                    conv_ok_sub, extracted_sub_ptp_content_folder, ptp_conv_err_msg_sub = self._run_ptp_converter(sub_ptp_file_to_process, nested_temp_sub_ptp_processing_dir)
                    if not conv_ok_sub: raise RuntimeError(ptp_conv_err_msg_sub or f"Conversion failed for sub-PTP: {ptp_filename_in_archive}")

                    # Read original aircraft.cfg/Config.cfg from source *before* reorganization for EOL detection, if possible
                    src_cfg_path = extracted_sub_ptp_content_folder / "Config.cfg"
                    if not src_cfg_path.is_file(): src_cfg_path = extracted_sub_ptp_content_folder / "aircraft.cfg"
                    if src_cfg_path.is_file():
                        with open(src_cfg_path, 'r', encoding='utf-8', errors='ignore') as f_orig_cfg:
                            original_cfg_for_eol_detection = f_orig_cfg.readlines()

                    reorg_ok_sub, reorg_msg_sub = self._reorganize_ptp_output(extracted_sub_ptp_content_folder)
                    if not reorg_ok_sub: raise RuntimeError(f"Reorganization failed for sub-PTP '{ptp_filename_in_archive}': {reorg_msg_sub}")

                    # _process_single_livery needs to return the path to the installed livery folder
                    # For now, we construct it based on its known naming convention.
                    # This part is crucial and might need _process_single_livery to return more info.
                    temp_sanitized_suffix = re.sub(r'[\\/*?:"<>|]', '_', livery_name_from_settings).strip().replace('.', '_')
                    if not temp_sanitized_suffix: temp_sanitized_suffix = f"UnnamedSubLivery_{sub_ptp_file_to_process.stem}"
                    
                    # This is the SimObjects folder for the current sub-livery
                    current_sub_livery_simobjects_folder_name = f"{common_config['base_aircraft_folder_name']} {temp_sanitized_suffix}"
                    current_sub_livery_installed_path = common_config['main_package_folder'] / "SimObjects" / "Airplanes" / current_sub_livery_simobjects_folder_name
                    
                    # Determine the texture folder name used by this sub-livery (e.g., from its aircraft.cfg's texture= line)
                    # This is simplified; a robust way would parse the aircraft.cfg *after* _process_single_livery runs.
                    # For now, assume it's often a known pattern or can be found.
                    # A common pattern is "texture.<atc_id>" or just "texture" or a specific name.
                    # This is a placeholder for robust texture folder name detection for the current sub-livery.
                    # We'll assume _process_single_livery handles copying the correct texture folder.
                    # The key is to find *its path* after installation.

                    livery_ok, detail = self._process_single_livery(
                        extracted_sub_ptp_content_folder,
                        sub_ptp_file_to_process,
                        common_config,
                        specific_livery_name=livery_name_from_settings
                    )

                    if livery_ok:
                        batch_success_counter[0] += 1
                        # Try to find the texture folder that was just installed for this sub-livery
                        # This requires knowing the name of the texture folder _process_single_livery would have copied.
                        # It's often based on the 'texture=' line in aircraft.cfg.
                        # This is a simplification:
                        temp_texture_folder_name = None
                        temp_aircraft_cfg_path = current_sub_livery_installed_path / "aircraft.cfg"
                        if temp_aircraft_cfg_path.is_file():
                            with open(temp_aircraft_cfg_path, 'r', encoding='utf-8', errors='ignore') as acfg_file:
                                for line_acfg in acfg_file:
                                    if line_acfg.strip().lower().startswith("texture="):
                                        temp_texture_folder_name = line_acfg.split("=")[1].strip()
                                        break
                        if temp_texture_folder_name:
                            current_sub_livery_installed_texture_folder_path = current_sub_livery_installed_path / temp_texture_folder_name
                        
                        if sub_livery_index == 0: # First successfully processed sub-livery in this pack
                            pack_base_livery_simobjects_folder_name = current_sub_livery_simobjects_folder_name
                            if current_sub_livery_installed_texture_folder_path and current_sub_livery_installed_texture_folder_path.is_dir():
                                pack_base_livery_texture_folder_name = current_sub_livery_installed_texture_folder_path.name
                                pack_base_livery_texture_folder_path = current_sub_livery_installed_texture_folder_path # Store full path
                                self.log(f"Set '{pack_base_livery_simobjects_folder_name}\\{pack_base_livery_texture_folder_name}' as potential texture base for this PTP pack.", "DETAIL")
                        elif pack_base_livery_texture_folder_path and current_sub_livery_installed_texture_folder_path and current_sub_livery_installed_texture_folder_path.is_dir():
                            # This is a subsequent livery, and we have a base. Add fallback.
                            self.log(f"Attempting to add fallback for '{livery_name_from_settings}' to base '{pack_base_livery_simobjects_folder_name}'.", "DETAIL")
                            self._add_texture_fallback_if_needed(
                                current_sub_livery_installed_texture_folder_path,
                                pack_base_livery_simobjects_folder_name,
                                pack_base_livery_texture_folder_name, # Name of texture folder in base
                                original_cfg_for_eol_detection
                            )
                    else: # livery_ok is False
                        batch_failure_flag_for_archive[0] = True
                    
                    results_summary_list.append({"file": display_name_for_log_and_summary, "success": livery_ok, "detail": detail})

                except Exception as e_sub_proc:
                    self.log(f"ERROR processing sub-PTP '{display_name_for_log_and_summary}': {e_sub_proc}", "ERROR")
                    results_summary_list.append({"file": display_name_for_log_and_summary, "success": False, "detail": str(e_sub_proc)})
                    batch_failure_flag_for_archive[0] = True
        
        else: # Single PTP structure
            self.log(f"Processing '{original_top_level_ptp_path.name}' as a single PTP structure.", "INFO")
            try:
                src_cfg_path = initial_ptp_extract_path / "Config.cfg"
                if not src_cfg_path.is_file(): src_cfg_path = initial_ptp_extract_path / "aircraft.cfg"
                original_cfg_for_eol_detection = None
                if src_cfg_path.is_file():
                    with open(src_cfg_path, 'r', encoding='utf-8', errors='ignore') as f_orig_cfg:
                        original_cfg_for_eol_detection = f_orig_cfg.readlines()

                reorg_ok, reorg_msg = self._reorganize_ptp_output(initial_ptp_extract_path)
                if not reorg_ok: raise RuntimeError(f"PTP reorganization failed: {reorg_msg}")
                
                livery_ok, detail = self._process_single_livery(initial_ptp_extract_path, original_top_level_ptp_path, common_config, specific_livery_name=None)
                results_summary_list.append({"file": original_top_level_ptp_path.name, "success": livery_ok, "detail": detail})
                if livery_ok: batch_success_counter[0] += 1
                else: batch_failure_flag_for_archive[0] = True
            except Exception as e_single_ptp_proc:
                self.log(f"ERROR processing single PTP structure from '{original_top_level_ptp_path.name}': {e_single_ptp_proc}", "ERROR")
                results_summary_list.append({"file": original_top_level_ptp_path.name, "success": False, "detail": str(e_single_ptp_proc)})
                batch_failure_flag_for_archive[0] = True

    def install_livery_logic(self, archive_paths_to_process: list[str]):
        num_files_initial = len(archive_paths_to_process)
        total_archives_processed_count = 0
        successful_liveries_installed_count_ref = [0] # Passed by reference to updating functions
        failed_top_level_archives_count = 0 # Counts top-level archives that had one or more errors

        results_summary: list[dict] = []

        # --- Common Configuration Setup ---
        try:
            community_path = Path(self.community_path_var.get())
            reference_livery_path = Path(self.reference_path_var.get())
            selected_variant_for_install = self.aircraft_variant_var.get()

            pmdg_localstate_base_package_path_str = ""
            if selected_variant_for_install.startswith("777"):
                if selected_variant_for_install == "777-200ER": pmdg_localstate_base_package_path_str = self.pmdg_77er_path_var.get()
                elif selected_variant_for_install == "777-300ER": pmdg_localstate_base_package_path_str = self.pmdg_77w_path_var.get()
                elif selected_variant_for_install == "777F": pmdg_localstate_base_package_path_str = self.pmdg_77f_path_var.get()
            elif selected_variant_for_install.startswith("737"):
                if "600" in selected_variant_for_install: pmdg_localstate_base_package_path_str = self.pmdg_736_path_var.get()
                elif "700" in selected_variant_for_install: pmdg_localstate_base_package_path_str = self.pmdg_737_path_var.get()
                elif "800" in selected_variant_for_install: pmdg_localstate_base_package_path_str = self.pmdg_738_path_var.get()
                elif "900" in selected_variant_for_install: pmdg_localstate_base_package_path_str = self.pmdg_739_path_var.get()

            if not pmdg_localstate_base_package_path_str:
                raise ValueError(f"PMDG Base Package Path for '{selected_variant_for_install}' is not set in Setup.")
            pmdg_localstate_for_variant_base_pkg = Path(pmdg_localstate_base_package_path_str)
            if not pmdg_localstate_for_variant_base_pkg.is_dir():
                raise ValueError(f"PMDG Base Package Path for '{selected_variant_for_install}' ('{pmdg_localstate_for_variant_base_pkg}') is not a valid directory.")

            target_community_package_name = VARIANT_PACKAGE_MAP.get(selected_variant_for_install)
            if not target_community_package_name:
                raise ValueError(f"Community package mapping missing for variant: {selected_variant_for_install}")
            target_community_package_root_path = community_path / target_community_package_name
            
            base_simobject_pmdg_folder_name = VARIANT_BASE_AIRCRAFT_MAP.get(selected_variant_for_install)
            if not base_simobject_pmdg_folder_name:
                raise ValueError(f"PMDG base SimObject folder name missing for variant: {selected_variant_for_install}")

            common_install_config = {
                'reference_livery_path': reference_livery_path,
                'pmdg_localstate_package_path': pmdg_localstate_for_variant_base_pkg,
                'aircraft_variant': selected_variant_for_install,
                'main_package_folder': target_community_package_root_path, # e.g., .../Community/pmdg-aircraft-737-liveries
                'base_aircraft_folder_name': base_simobject_pmdg_folder_name, # e.g., PMDG 737-700
            }

            target_community_package_root_path.mkdir(parents=True, exist_ok=True)
            manifest_path_in_package = target_community_package_root_path / "manifest.json"
            layout_path_in_package = target_community_package_root_path / "layout.json"

            if not manifest_path_in_package.exists():
                ref_manifest_path = reference_livery_path / "manifest.json"
                if not ref_manifest_path.is_file():
                    raise FileNotFoundError(f"Reference manifest.json missing at '{reference_livery_path}' and no destination manifest exists for '{target_community_package_name}'.")
                shutil.copy2(ref_manifest_path, manifest_path_in_package)
                self.log(f"Copied manifest.json from reference to '{manifest_path_in_package}'", "INFO")
            
            try:
                dependency_name_for_manifest = VARIANT_DEPENDENCY_MAP.get(selected_variant_for_install)
                if not dependency_name_for_manifest:
                    self.log(f"Dependency mapping missing for '{selected_variant_for_install}'. Manifest may be incomplete.", "ERROR")
                    dep_list = []
                else:
                    dep_list = [{"name": dependency_name_for_manifest, "package_version": "0.1.0"}] # Example version

                with open(manifest_path_in_package, 'r+', encoding='utf-8') as f:
                    m_data = json.load(f)
                    m_data.update({
                        "dependencies": dep_list,
                        "content_type": "LIVERY",
                        "title": f"Livery Pack: {base_simobject_pmdg_folder_name.replace('PMDG ', '')}", # Cleaner title
                        "manufacturer": m_data.get("manufacturer", "PMDG"), # Preserve if exists
                        "creator": f"Livery Installer {self.app_version}",
                        "package_version": m_data.get("package_version", "1.0.0"), # Preserve if exists
                        "minimum_game_version": DEFAULT_MIN_GAME_VERSION,
                    })
                    f.seek(0)
                    json.dump(m_data, f, indent=4)
                    f.truncate()
                self.log(f"Manifest.json for '{target_community_package_name}' updated/initialized.", "SUCCESS")
            except Exception as e_mf_init:
                self.log(f"ERROR updating manifest.json for '{target_community_package_name}': {e_mf_init}", "ERROR")
                # Decide if this is critical enough to stop; for now, it logs and continues

            if not layout_path_in_package.exists() and (reference_livery_path / "layout.json").is_file():
                shutil.copy2(reference_livery_path / "layout.json", layout_path_in_package)
                self.log(f"Copied layout.json from reference to '{layout_path_in_package}'", "INFO")

        except Exception as config_err:
            self.log(f"CRITICAL SETUP ERROR: {config_err}", "ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "DETAIL")
            self.master.after(0, lambda: self.status_var.set("Installation failed! (Setup Error)"))
            self.master.after(0, lambda: self.install_button.config(state=tk.NORMAL))
            messagebox.showerror("Critical Error", f"Could not configure installation environment:\n{config_err}")
            return

        # --- Main loop to process each selected archive file ---
        for idx, archive_file_path_str in enumerate(archive_paths_to_process):
            original_archive_path = Path(archive_file_path_str)
            log_archive_name = original_archive_path.name
            self.log(f"--- Processing Archive: {log_archive_name} ({idx + 1}/{num_files_initial}) ---", "STEP")
            self.master.after(0, lambda i=idx, n=log_archive_name: self.status_var.set(f"Processing {i+1}/{num_files_initial}: {n}..."))

            # Temporary base directory for this specific archive's processing
            # Placed inside the target community package to handle long paths better if Community is on a drive with long paths enabled.
            archive_temp_base = target_community_package_root_path / f"__temp_archive_{original_archive_path.stem}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            
            current_top_level_archive_had_failure = [False] # Mutable flag to track if any sub-process for this archive fails

            try: # This try block is for the processing of a single top-level archive
                archive_temp_base.mkdir(parents=True, exist_ok=True)

                if original_archive_path.suffix.lower() == ".ptp":
                    conv_ok, initial_extract_folder, ptp_conv_err_msg = self._run_ptp_converter(original_archive_path, archive_temp_base)
                    if not conv_ok:
                        error_detail = ptp_conv_err_msg if ptp_conv_err_msg else f"Initial PTP conversion failed for {log_archive_name}."
                        raise RuntimeError(error_detail)
                    
                    # initial_extract_folder is where _run_ptp_converter has staged the PTP's content
                    self._process_extracted_ptp_content(
                        initial_extract_folder,
                        original_archive_path, # Pass the original top-level PTP path for context
                        common_install_config,
                        results_summary,
                        successful_liveries_installed_count_ref,
                        current_top_level_archive_had_failure # This flag will be set if any sub-livery fails
                    )
                
                elif original_archive_path.suffix.lower() == ".zip":
                    zip_extract_target_dir = archive_temp_base / f"__extracted_zip_{original_archive_path.stem}"
                    zip_extract_target_dir.mkdir(parents=True, exist_ok=True)
                    self._extract_archive(original_archive_path, zip_extract_target_dir)

                    # Determine the effective content directory (handles ZIPs with a single root folder)
                    items_in_zip_extract = list(zip_extract_target_dir.iterdir())
                    effective_content_dir_for_zip = zip_extract_target_dir
                    if len(items_in_zip_extract) == 1 and items_in_zip_extract[0].is_dir() and \
                       not items_in_zip_extract[0].name.startswith(('.', '__MACOSX', '__temp_')):
                        effective_content_dir_for_zip = items_in_zip_extract[0]

                    if self._is_nested_archive(effective_content_dir_for_zip):
                        self.log(f"'{log_archive_name}' is a ZIP pack. Processing nested archives...", "INFO")
                        nested_archives = list(effective_content_dir_for_zip.glob('*.zip')) + \
                                          list(effective_content_dir_for_zip.glob('*.ptp'))
                        if not nested_archives:
                            self.log(f"Pack '{log_archive_name}' contains no processable sub-archives.", "WARNING")
                            results_summary.append({"file": log_archive_name, "success": False, "detail": "ZIP Pack empty or no recognized sub-archives."})
                            current_top_level_archive_had_failure[0] = True
                        else:
                            for nested_idx, nested_archive_path_obj in enumerate(nested_archives):
                                nested_log_name_display = f"{log_archive_name} -> {nested_archive_path_obj.name}"
                                self.log(f"--- Nested {nested_idx + 1}/{len(nested_archives)}: {nested_archive_path_obj.name} ---", "STEP")
                                
                                # Create a unique temp subdir for this nested archive's processing
                                nested_temp_sub_proc_dir = archive_temp_base / f"__zip_nested_proc_{nested_archive_path_obj.stem}_{nested_idx}_{datetime.now().strftime('%f')}"
                                try:
                                    nested_temp_sub_proc_dir.mkdir(parents=True, exist_ok=True)
                                    
                                    if nested_archive_path_obj.suffix.lower() == ".ptp":
                                        # Handle PTP nested within a ZIP
                                        s_conv_ok, s_conv_folder, s_ptp_err = self._run_ptp_converter(nested_archive_path_obj, nested_temp_sub_proc_dir)
                                        if not s_conv_ok:
                                            s_err_detail = s_ptp_err if s_ptp_err else f"PTP conversion failed for nested {nested_archive_path_obj.name}"
                                            raise RuntimeError(s_err_detail)
                                        
                                        self._process_extracted_ptp_content(
                                            s_conv_folder,
                                            nested_archive_path_obj, # Pass the path of the nested PTP itself
                                            common_install_config,
                                            results_summary,
                                            successful_liveries_installed_count_ref,
                                            current_top_level_archive_had_failure # If any sub-PTP fails, it flags the main archive
                                        )
                                    elif nested_archive_path_obj.suffix.lower() == ".zip":
                                        # Handle ZIP nested within a ZIP (assuming it's a single livery)
                                        nested_zip_extract_target = nested_temp_sub_proc_dir / f"__extracted_sub_zip_{nested_archive_path_obj.stem}"
                                        nested_zip_extract_target.mkdir(exist_ok=True)
                                        self._extract_archive(nested_archive_path_obj, nested_zip_extract_target)
                                        
                                        items_in_sub_extract = list(nested_zip_extract_target.iterdir())
                                        prepared_sub_archive_folder = nested_zip_extract_target
                                        if len(items_in_sub_extract) == 1 and items_in_sub_extract[0].is_dir() and not items_in_sub_extract[0].name.startswith(('.', '__MACOSX')):
                                            prepared_sub_archive_folder = items_in_sub_extract[0]
                                        
                                        if prepared_sub_archive_folder:
                                            # For nested ZIPs, specific_livery_name is None; _process_single_livery will auto-detect.
                                            liv_ok, det = self._process_single_livery(prepared_sub_archive_folder, nested_archive_path_obj, common_install_config)
                                            results_summary.append({"file": nested_log_name_display, "success": liv_ok, "detail": det})
                                            if liv_ok:
                                                successful_liveries_installed_count_ref[0] += 1
                                            else:
                                                current_top_level_archive_had_failure[0] = True
                                        else:
                                            raise RuntimeError(f"Could not prepare content from nested ZIP: {nested_archive_path_obj.name}")
                                except Exception as e_nest_proc:
                                    self.log(f"ERROR processing nested archive '{nested_archive_path_obj.name}': {e_nest_proc}", "ERROR")
                                    results_summary.append({"file": nested_log_name_display, "success": False, "detail": str(e_nest_proc)})
                                    current_top_level_archive_had_failure[0] = True
                                # No explicit cleanup of nested_temp_sub_proc_dir here, as it's inside archive_temp_base
                    else: # Simple (non-nested) ZIP
                        # For a top-level simple ZIP, specific_livery_name is None.
                        livery_ok, detail = self._process_single_livery(effective_content_dir_for_zip, original_archive_path, common_install_config)
                        results_summary.append({"file": log_archive_name, "success": livery_ok, "detail": detail})
                        if livery_ok:
                            successful_liveries_installed_count_ref[0] += 1
                        else:
                            current_top_level_archive_had_failure[0] = True
                else:
                    raise ValueError(f"Unsupported archive type: {log_archive_name}")

            except Exception as e_archive_proc:
                self.log(f"ERROR processing archive '{log_archive_name}': {e_archive_proc}", "ERROR")
                import traceback
                self.log(f"Traceback for archive processing error: {traceback.format_exc()}", "DETAIL")
                # Ensure a result is added for the top-level archive if its processing fails early
                if not any(r["file"] == log_archive_name for r in results_summary): # Avoid duplicate summary for top-level
                     results_summary.append({"file": log_archive_name, "success": False, "detail": str(e_archive_proc)})
                current_top_level_archive_had_failure[0] = True
            finally:
                # This finally block is for the try block processing a single top-level archive
                self.log(f"Attempting to clean temp dir for archive '{log_archive_name}': {archive_temp_base}", "DETAIL")
                if archive_temp_base.exists():
                    try:
                        shutil.rmtree(archive_temp_base)
                        self.log(f"Successfully cleaned temp dir: {archive_temp_base}", "DETAIL")
                    except Exception as e_clean:
                        self.log(f"Error cleaning temp dir '{archive_temp_base.name}': {e_clean}", "WARNING")
                        # Log more details if cleanup fails, as it might indicate locked files
                        import traceback
                        self.log(f"Traceback for temp dir cleanup error: {traceback.format_exc()}", "DETAIL")
                else:
                    self.log(f"Temp dir not found for cleaning (already cleaned or never fully created): {archive_temp_base}", "DETAIL")
            
            total_archives_processed_count += 1
            if current_top_level_archive_had_failure[0]:
                failed_top_level_archives_count += 1
            
            progress = ((idx + 1) / num_files_initial) * 85.0 # 85% for processing, 15% for layout/manifest
            self.master.after(0, lambda p=progress: self.progress_var.set(p))
        # --- End of loop for processing each selected archive file ---

        final_successful_liveries = successful_liveries_installed_count_ref[0]
        layout_manifest_ok = False
        final_post_proc_msg = ""

        if final_successful_liveries > 0 and failed_top_level_archives_count == 0:
            self.log(f"All {final_successful_liveries} livery(s) from {total_archives_processed_count} archive(s) appear to have installed correctly. Generating layout/manifest...", "STEP")
            try:
                layout_ok, layout_err, content_total_size, layout_file_size = self._generate_layout_file(target_community_package_root_path)
                if layout_ok:
                    self.master.after(0, lambda: self.progress_var.set(95))
                    self.master.after(0, lambda: self.status_var.set("Updating manifest.json..."))
                    
                    manifest_actual_size = 0
                    if manifest_path_in_package.is_file():
                        manifest_actual_size = manifest_path_in_package.stat().st_size
                    
                    total_package_size_for_manifest = content_total_size + layout_file_size + manifest_actual_size
                    
                    manifest_ok = self._update_manifest_file(manifest_path_in_package, total_package_size_for_manifest)
                    if manifest_ok:
                        layout_manifest_ok = True
                        self.master.after(0, lambda: self.progress_var.set(100))
                        final_post_proc_msg = "Layout.json and manifest.json generated/updated successfully."
                        self.log(final_post_proc_msg, "SUCCESS")
                    else:
                        final_post_proc_msg = "Failed to update manifest.json total_package_size."
                        self.log(final_post_proc_msg, "ERROR")
                else:
                    final_post_proc_msg = f"Failed to generate layout.json: {layout_err}"
                    self.log(final_post_proc_msg, "ERROR")
            except Exception as e_post_proc:
                final_post_proc_msg = f"Error during layout/manifest generation: {e_post_proc}"
                self.log(final_post_proc_msg, "ERROR")
                import traceback
                self.log(f"Traceback for post-processing error: {traceback.format_exc()}", "DETAIL")
        elif final_successful_liveries > 0: # Some liveries installed, but some top-level archives had errors
            final_post_proc_msg = (f"Partial success. {failed_top_level_archives_count} of {total_archives_processed_count} top-level archive(s) had errors. "
                                   "Layout/manifest NOT updated for the package. Installed liveries from successful archives might work, "
                                   "but the overall package state is inconsistent.")
            self.log(final_post_proc_msg, "WARNING")
            self.master.after(0, lambda: self.progress_var.set(100)) # Mark progress as done, but with issues
        elif total_archives_processed_count > 0: # All top-level archives failed or yielded no liveries
            final_post_proc_msg = "All installations failed or archives yielded no liveries. Layout/manifest NOT updated."
            self.log(final_post_proc_msg, "ERROR")
            self.master.after(0, lambda: self.progress_var.set(100))
        else: # No files were processed (e.g., user didn't select any)
            final_post_proc_msg = "No files selected or processed. No updates made."
            self.log(final_post_proc_msg, "INFO")
            self.master.after(0, lambda: self.progress_var.set(100))

        # --- Final Status Update and Message ---
        final_status_message = "No files processed."
        if total_archives_processed_count > 0:
            if failed_top_level_archives_count == 0 and layout_manifest_ok:
                final_status_message = "Completed successfully!"
            elif final_successful_liveries > 0:
                final_status_message = "Completed with errors."
            else:
                final_status_message = "All operations failed."
        
        self.master.after(0, lambda s=final_status_message: self.status_var.set(s))
        self.master.after(100, lambda: self.show_multi_final_message(results_summary, layout_manifest_ok, final_post_proc_msg, str(target_community_package_root_path)))
        self.master.after(200, self._finalize_installation_ui)


    def _finalize_installation_ui(self):
        """Resets UI elements after an installation attempt."""
        self.install_button.config(state=tk.NORMAL)
        self._reset_install_fields()
        self.log("Batch installation process finished. Ready for new operation.", "STEP")

    def _reset_install_fields(self):
        self.log("Resetting install tab fields.", "DETAIL")
        self.selected_zip_files = []
        self.livery_zip_display_var.set("")
        self.custom_name_var.set("")
        if hasattr(self, 'custom_name_entry') and self.custom_name_entry.winfo_exists():
             self.custom_name_entry.config(state=tk.NORMAL)
        # Optionally, clear aircraft selection or leave for convenience
        # self.aircraft_series_var.set("")
        # self.variant_combobox.set("")
        # self.variant_combobox.config(state='disabled', values=[])
        # self.aircraft_variant_var.set("")

    def modify_aircraft_cfg(self, cfg_path: Path, aircraft_variant_selected: str, livery_title_from_detection: str):
        """
        Modifies the aircraft.cfg file at cfg_path.
        - Ensures [FLTSIM.0] title matches livery_title_from_detection, correcting "ttitle".
        - Normalizes malformed [fltsim.x] headers (e.g., [[fltsim.0]]).
        - Ensures [VARIATION] base_container is correct for the aircraft_variant_selected.
        - Attempts to place a missing [VARIATION] section after [VERSION] or before [FLTSIM.0].
        - Ensures a [VERSION] section exists, prepending if necessary.
        """
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Cannot modify aircraft.cfg, file not found: {cfg_path}")

        self.log(f"Modifying aircraft.cfg: {cfg_path.name} for variant {aircraft_variant_selected}, title '{livery_title_from_detection}'", "INFO")

        cfg_base_container_name_from_map = AIRCRAFT_CFG_BASE_CONTAINER_MAP.get(aircraft_variant_selected)
        if not cfg_base_container_name_from_map:
            raise ValueError(f"Invalid variant '{aircraft_variant_selected}' for aircraft.cfg base_container lookup in AIRCRAFT_CFG_BASE_CONTAINER_MAP.")

        try:
            with open(cfg_path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
                lines = f.readlines()
        except Exception as e:
            raise RuntimeError(f"Error reading aircraft.cfg file '{cfg_path}': {e}")

        eol_char = '\n'  # Default EOL
        if lines and lines[0].endswith('\r\n'): # Detect EOL from first line if possible
            eol_char = '\r\n'
        elif lines and len(lines) > 1 and lines[1].endswith('\r\n'): # Or second line
             eol_char = '\r\n'
        # CAMBIO: Detectar EOL de manera más robusta si las primeras líneas están vacías
        elif lines:
            for line_check_eol in lines:
                if line_check_eol.endswith('\r\n'):
                    eol_char = '\r\n'
                    break
                if line_check_eol.endswith('\n'): # No need to break, \n is default
                    eol_char = '\n' # Explicitly set if found before any \r\n
                    # We don't break here in case a \r\n is found later, which would take precedence.
                    # However, mixed EOLs are bad. This aims for consistency based on first dominant style.
                    # A more robust solution would be to normalize all EOLs to one style first.
                    # For now, this prioritizes \r\n if found anywhere early.
            self.log(f"Detected EOL for {cfg_path.name} as: {repr(eol_char)}", "DETAIL")


        target_variation_base_container_value = f'"..\\{cfg_base_container_name_from_map}"'
        if aircraft_variant_selected == "777-200ER": # Special handling for 777-200ER engine variants
            original_bc_line_content = None
            temp_in_variation_check = False
            for line_r_check in lines:
                s_line_r_check = line_r_check.strip()
                if s_line_r_check.lower() == '[variation]': temp_in_variation_check = True; continue
                if temp_in_variation_check:
                    if s_line_r_check.startswith('['): break
                    if re.match(r'^\s*base_container\s*=', s_line_r_check, re.IGNORECASE):
                        original_bc_line_content = s_line_r_check; break
            if original_bc_line_content:
                bc_match_check = re.match(r'^\s*base_container\s*=\s*"?(.+?)"?\s*$', original_bc_line_content, re.IGNORECASE)
                if bc_match_check:
                    existing_val_check = bc_match_check.group(1).strip().replace('/', '\\')
                    engine_suffix_match_check = re.search(rf'{re.escape(cfg_base_container_name_from_map)}\s+(GE|RR|PW)\b', existing_val_check, re.IGNORECASE)
                    if engine_suffix_match_check:
                        engine_code_check = engine_suffix_match_check.group(1).upper()
                        target_variation_base_container_value = f'"..\\{cfg_base_container_name_from_map} {engine_code_check}"'
                        self.log(f"777-200ER: Will use engine suffix '{engine_code_check}' for base_container.", "DETAIL")

        # CAMBIO: Sanitize livery_title_from_detection to prevent issues with quotes in the title value
        safe_livery_title = livery_title_from_detection.replace('"', "'") # Replace double quotes with single quotes
        if '"' in livery_title_from_detection:
            self.log(f"Sanitized livery title from '{livery_title_from_detection}' to '{safe_livery_title}'", "DETAIL")

        final_target_bc_line_to_write = f'base_container = {target_variation_base_container_value}'
        final_target_title_line_to_write = f'title = "{safe_livery_title}"' # Use sanitized title
        self.log(f"Target aircraft.cfg [VARIATION] base_container: {final_target_bc_line_to_write}", "DETAIL")
        self.log(f"Target aircraft.cfg [FLTSIM.0] title: {final_target_title_line_to_write}", "DETAIL")

        output_lines = []
        needs_rewrite = False

        in_fltsim0 = False; title_handled_current_section = False
        in_variation = False; base_container_handled_current_section = False

        original_version_exists = any(line.strip().lower() == '[version]' for line in lines)
        original_variation_exists = any(line.strip().lower() == '[variation]' for line in lines)
        fltsim0_processed_or_normalized = False

        idx = 0
        while idx < len(lines):
            line_content = lines[idx]
            stripped = line_content.strip()
            s_line_lower = stripped.lower()
            # CAMBIO: Capture indent more reliably, even for empty lines, use original line_content for EOL
            indent = line_content[:len(line_content) - len(line_content.lstrip())]


            fltsim_header_match = re.match(r'^\s*(\[{1,2})fltsim\.([0-9]+)(\]{1,2})', s_line_lower, re.IGNORECASE) # CAMBIO: Capture fltsim number if needed, though we force .0

            if s_line_lower == '[version]':
                if in_fltsim0 and not title_handled_current_section: output_lines.append(f"{indent}{final_target_title_line_to_write}{eol_char}"); title_handled_current_section=True; needs_rewrite = True # Mark as handled
                if in_variation and not base_container_handled_current_section: output_lines.append(f"{indent}{final_target_bc_line_to_write}{eol_char}"); base_container_handled_current_section=True; needs_rewrite = True
                in_fltsim0 = False; in_variation = False
                output_lines.append(line_content)
            elif s_line_lower == '[variation]':
                if in_fltsim0 and not title_handled_current_section: output_lines.append(f"{indent}{final_target_title_line_to_write}{eol_char}"); title_handled_current_section=True; needs_rewrite = True
                in_fltsim0 = False; in_variation = True; base_container_handled_current_section = False # Reset for this new section
                output_lines.append(line_content)
            elif fltsim_header_match:
                if in_fltsim0 and not title_handled_current_section: output_lines.append(f"{indent}{final_target_title_line_to_write}{eol_char}"); title_handled_current_section=True; needs_rewrite = True
                if in_variation and not base_container_handled_current_section: output_lines.append(f"{indent}{final_target_bc_line_to_write}{eol_char}"); base_container_handled_current_section=True; needs_rewrite = True

                # CAMBIO: Explicitly write the corrected header and DO NOT write the original line_content for this line
                normalized_header_content = f"[fltsim.0]" # We always want fltsim.0 for liveries from this tool
                if stripped != normalized_header_content: # Check if it was different from "[fltsim.0]"
                    self.log(f"Normalized FLTSIM header from '{stripped}' to '{normalized_header_content}'.", "INFO")
                    needs_rewrite = True
                output_lines.append(f"{indent}{normalized_header_content}{eol_char}")

                in_fltsim0 = True; title_handled_current_section = False; in_variation = False
                fltsim0_processed_or_normalized = True
            elif stripped.startswith('['): # Other sections
                if in_fltsim0 and not title_handled_current_section: output_lines.append(f"{indent}{final_target_title_line_to_write}{eol_char}"); title_handled_current_section=True; needs_rewrite = True
                if in_variation and not base_container_handled_current_section: output_lines.append(f"{indent}{final_target_bc_line_to_write}{eol_char}"); base_container_handled_current_section=True; needs_rewrite = True
                in_fltsim0 = False; in_variation = False
                output_lines.append(line_content)
            elif in_fltsim0:
                if re.match(r'^\s*t?title\s*=', stripped, re.IGNORECASE): # Line is a title line
                    # CAMBIO: Explicitly write the corrected title line and DO NOT write the original line_content
                    # Check if the content (key and value) is already exactly what we want.
                    # final_target_title_line_to_write already has 'title = "value"'
                    if stripped.lower() != final_target_title_line_to_write.lower(): # Case insensitive compare for content
                        self.log(f"Corrected/Updated 'title' in [FLTSIM.0]. Original: '{stripped}'. Target: '{final_target_title_line_to_write}'.", "INFO")
                        output_lines.append(f"{indent}{final_target_title_line_to_write}{eol_char}")
                        needs_rewrite = True
                    else: # Already correct
                        output_lines.append(line_content)
                    title_handled_current_section = True
                else: # Other lines within [fltsim.0]
                    output_lines.append(line_content)
            elif in_variation:
                if re.match(r'^\s*base_container\s*=', stripped, re.IGNORECASE): # Line is a base_container line
                    # CAMBIO: Explicitly write the corrected base_container line
                    if stripped.lower() != final_target_bc_line_to_write.lower(): # Case insensitive compare for content
                        self.log(f"Corrected/Updated 'base_container=' in [VARIATION]. Original: '{stripped}'. Target: '{final_target_bc_line_to_write}'.", "INFO")
                        output_lines.append(f"{indent}{final_target_bc_line_to_write}{eol_char}")
                        needs_rewrite = True
                    else: # Already correct
                        output_lines.append(line_content)
                    base_container_handled_current_section = True
                else: # Other lines within [VARIATION]
                    output_lines.append(line_content)
            else: # Lines outside any recognized section or before any section
                output_lines.append(line_content)
            idx += 1

        # After loop, handle cases where sections might have been implicitly closed by EOF
        if in_fltsim0 and not title_handled_current_section:
            # CAMBIO: Use a default indent if current 'indent' is unreliable (e.g. from a blank last line)
            output_lines.append(f"    {final_target_title_line_to_write}{eol_char}") # Default to 4 spaces indent
            self.log("Added 'title=' at end of [FLTSIM.0] (EOF).", "INFO"); needs_rewrite = True
            fltsim0_processed_or_normalized = True
        if in_variation and not base_container_handled_current_section:
            output_lines.append(f"    {final_target_bc_line_to_write}{eol_char}") # Default to 4 spaces indent
            self.log("Added 'base_container=' at end of [VARIATION] (EOF).", "INFO"); needs_rewrite = True

        # Ensure [VERSION] section exists
        if not original_version_exists:
            self.log("Prepending missing [VERSION] section.", "INFO")
            new_version_content = [f"[VERSION]{eol_char}", f"major=1{eol_char}", f"minor=0{eol_char}"]
            # Add a blank line after [VERSION] if there's content following and it's not already blank
            if output_lines and output_lines[0].strip() != "":
                 new_version_content.append(eol_char)
            output_lines = new_version_content + output_lines
            needs_rewrite = True

        # Ensure [VARIATION] section exists and is correctly populated
        if not original_variation_exists:
            self.log("Attempting to insert missing [VARIATION] section.", "INFO")
            new_variation_section_lines = [f"[VARIATION]{eol_char}", f"    {final_target_bc_line_to_write}{eol_char}"] # Default 4 spaces
            inserted = False
            # Try to insert after [VERSION]
            version_section_end_index = -1
            for i, line_out in enumerate(output_lines):
                if line_out.strip().lower() == '[version]':
                    j = i + 1
                    while j < len(output_lines) and not output_lines[j].strip().startswith('['):
                        j += 1
                    version_section_end_index = j
                    break
            if version_section_end_index != -1 :
                # Add blank line before [VARIATION] if needed
                prefix_space = [eol_char] if version_section_end_index > 0 and output_lines[version_section_end_index-1].strip() != "" else []
                # Add blank line after [VARIATION] if needed
                suffix_space = [eol_char] if version_section_end_index < len(output_lines) and output_lines[version_section_end_index].strip() != "" else []
                output_lines = output_lines[:version_section_end_index] + prefix_space + new_variation_section_lines + suffix_space + output_lines[version_section_end_index:]
                self.log("Inserted [VARIATION] section after [VERSION].", "DETAIL"); inserted = True; needs_rewrite = True
            else: # Fallback: insert before [FLTSIM.0] or append
                fltsim0_start_index = -1
                for i, line_out in enumerate(output_lines):
                    if line_out.strip().lower() == '[fltsim.0]': # Match the corrected one
                        fltsim0_start_index = i; break
                if fltsim0_start_index != -1:
                    prefix_space = [eol_char] if fltsim0_start_index > 0 and output_lines[fltsim0_start_index-1].strip() != "" else []
                    suffix_space = [eol_char] # Always add a space after variation if before fltsim
                    output_lines = output_lines[:fltsim0_start_index] + prefix_space + new_variation_section_lines + suffix_space + output_lines[fltsim0_start_index:]
                    self.log("Inserted [VARIATION] section before [FLTSIM.0].", "DETAIL"); inserted = True; needs_rewrite = True
                else: # Absolute fallback: append
                    if output_lines and output_lines[-1].strip() != "": output_lines.append(eol_char)
                    output_lines.extend(new_variation_section_lines)
                    self.log("Appended [VARIATION] section (fallback).", "DETAIL"); needs_rewrite = True
            original_variation_exists = True # To prevent re-adding if fltsim0 also needs adding

        # Ensure [FLTSIM.0] section exists if it wasn't processed
        if not fltsim0_processed_or_normalized: # If no [fltsim.X] was found and normalized
            self.log("Adding missing [FLTSIM.0] section as none was found or normalized.", "INFO")
            if output_lines and output_lines[-1].strip() != "": output_lines.append(eol_char) # Ensure blank line before new section
            output_lines.append(f"[FLTSIM.0]{eol_char}")
            output_lines.append(f"    {final_target_title_line_to_write}{eol_char}") # Default 4 spaces
            # CAMBIO: Add other essential fields if adding FLTSIM.0 from scratch, copying structure from example
            # These would ideally come from the PTP or be intelligently defaulted
            # For now, ensure title is there. Other values would need more complex logic or templates.
            # Example:
            # output_lines.append(f"    model={''}{eol_char}") # Requires model detection
            # output_lines.append(f"    texture={''}{eol_char}") # Requires texture detection
            # output_lines.append(f"    sim={AIRCRAFT_SIM_MAP.get(aircraft_variant_selected, '')}{eol_char}") # Needs a new map
            needs_rewrite = True


        # Final check if content actually changed, in case of subtle EOL normalization only
        if not needs_rewrite:
            original_content_for_comparison = "".join(lines)
            new_content_for_comparison = "".join(output_lines)
            if original_content_for_comparison != new_content_for_comparison:
                self.log("Content mismatch detected (e.g. EOL normalization), marking for rewrite.", "DETAIL")
                needs_rewrite = True

        if needs_rewrite:
            try:
                with open(cfg_path, 'w', encoding='utf-8', errors='ignore', newline='') as f_w:
                    f_w.writelines(output_lines)
                self.log(f"aircraft.cfg '{cfg_path.name}' saved with modifications.", "SUCCESS")
            except Exception as e_write:
                self.log(f"CRITICAL ERROR writing modified aircraft.cfg '{cfg_path.name}': {e_write}", "ERROR")
                # Optionally re-raise or handle more gracefully
        else:
            self.log(f"No modifications deemed necessary for aircraft.cfg '{cfg_path.name}'.", "DETAIL")

    def _generate_layout_file(self, package_root_path: Path) -> tuple[bool, str, int, int]:
        self.log(f"Generating layout.json for: {package_root_path}", "STEP")
        content_entries = []
        files_scanned_count = 0
        content_total_size = 0
        layout_file_size_on_disk = 0
        layout_json_path = package_root_path / "layout.json"
        excluded_dir_prefixes = ("__temp_",) # Temp folders created by this tool

        try:
            for root_str, dirs, files in os.walk(str(package_root_path), topdown=True):
                dirs[:] = [d for d in dirs if not d.startswith(excluded_dir_prefixes)]
                current_root_path = Path(root_str)
                
                for filename in files:
                    files_scanned_count += 1
                    if files_scanned_count % 200 == 0:
                        self.log(f"    ... {files_scanned_count} files scanned for layout...", "DETAIL")

                    file_abs_path = current_root_path / filename
                    try:
                        rel_path_str = file_abs_path.relative_to(package_root_path).as_posix()
                        if rel_path_str.lower() in ('layout.json', 'manifest.json') or \
                           filename.startswith('.') or filename.lower() == 'thumbs.db':
                            continue
                        
                        file_stat = file_abs_path.stat()
                        content_entries.append({
                            "path": rel_path_str, "size": file_stat.st_size,
                            "date": _unix_to_filetime(file_stat.st_mtime)
                        })
                        content_total_size += file_stat.st_size
                    except Exception as e_file:
                        self.log(f"Warning: Error processing file '{file_abs_path}' for layout: {e_file}. Skipping.", "WARNING")
            
            self.log(f"Layout scan complete. {len(content_entries)} files included. Total content size: {content_total_size} bytes.", "INFO")
            content_entries.sort(key=lambda x: x['path'])
            
            with open(layout_json_path, 'w', encoding='utf-8', newline='\n') as f_out:
                json.dump({"content": content_entries}, f_out, indent=4)
            self.log(f"{layout_json_path.name} generated/updated successfully.", "SUCCESS")
            layout_file_size_on_disk = layout_json_path.stat().st_size
            return True, "", content_total_size, layout_file_size_on_disk
        except Exception as e_main:
            err_msg = f"CRITICAL error during layout.json generation for '{package_root_path}': {e_main}"
            self.log(err_msg, "ERROR"); import traceback; self.log(f"Traceback: {traceback.format_exc()}", "DETAIL")
            return False, str(e_main), 0, 0

    def _update_manifest_file(self, manifest_path: Path, calculated_total_package_size: int) -> bool:
        self.log(f"Updating manifest.json: {manifest_path} with total size: {calculated_total_package_size}", "STEP")
        try:
            if not manifest_path.is_file():
                self.log(f"Error: {manifest_path.name} not found. Cannot update size.", "ERROR"); return False
            
            with open(manifest_path, 'r+', encoding='utf-8') as f:
                manifest_data = json.load(f)
                if not isinstance(manifest_data, dict):
                    self.log(f"Error: {manifest_path.name} is not valid JSON.", "ERROR"); return False

                new_size_str = f"{calculated_total_package_size:020d}" # Padded to 20 digits
                manifest_data['total_package_size'] = new_size_str
                # Update release notes last update time
                if "release_notes" not in manifest_data or not isinstance(manifest_data["release_notes"], dict):
                    manifest_data["release_notes"] = {"neutral": {}}
                if "neutral" not in manifest_data["release_notes"] or not isinstance(manifest_data["release_notes"]["neutral"], dict):
                     manifest_data["release_notes"]["neutral"] = {}
                manifest_data["release_notes"]["neutral"]["LastUpdate"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


                f.seek(0); json.dump(manifest_data, f, indent=4); f.truncate()
                self.log(f"'total_package_size' and 'LastUpdate' in {manifest_path.name} updated successfully.", "SUCCESS")
            return True
        except Exception as e_gen:
            self.log(f"CRITICAL error updating {manifest_path.name}: {e_gen}", "ERROR")
            import traceback; self.log(f"Traceback: {traceback.format_exc()}", "DETAIL")
            return False

    def show_multi_final_message(self, results: list[dict], layout_manifest_pkg_postproc_success: bool, layout_manifest_pkg_postproc_detail: str, community_pkg_path_str: str):
        successful_individual_liveries = sum(1 for r in results if r["success"])
        failed_individual_liveries_or_archives = len(results) - successful_individual_liveries
        total_processed_input_archives = len(self.selected_zip_files)

        title = "Installation Batch Result"
        summary_lines = []
        log_level_for_summary_msg = "INFO"
        messagebox_func = messagebox.showinfo

        if not results and total_processed_input_archives == 0:
            summary_lines.append("No livery archive files were selected or no operations were performed.")
        elif failed_individual_liveries_or_archives == 0 :
            if layout_manifest_pkg_postproc_success:
                summary_lines.append(f"All {successful_individual_liveries} livery(s) (from {total_processed_input_archives} archive(s)) installed successfully!")
                summary_lines.append(f"Package layout.json and manifest.json for '{Path(community_pkg_path_str).name}' also generated/updated.")
                summary_lines.append("\nThe livery/liveries should now be available in MSFS (restart MSFS if running).")
                log_level_for_summary_msg = "SUCCESS"
            else: 
                summary_lines.append(f"All {successful_individual_liveries} livery(s) were copied, BUT package post-processing (layout/manifest) failed!")
                summary_lines.append(f"\nPackage Finalization Error: {layout_manifest_pkg_postproc_detail}")
                summary_lines.append("\nLiveries might NOT appear correctly. Check log and Help tab.")
                log_level_for_summary_msg = "ERROR"; messagebox_func = messagebox.showerror
        else: 
            summary_lines.append(f"Batch completed with {failed_individual_liveries_or_archives} error(s) out of {total_processed_input_archives} archive(s).")
            summary_lines.append(f" - Successful individual liveries: {successful_individual_liveries}")
            summary_lines.append(f" - Failed items: {failed_individual_liveries_or_archives}")
            
            if layout_manifest_pkg_postproc_detail:
                 summary_lines.append(f"\nPackage Layout/Manifest Status: {layout_manifest_pkg_postproc_detail}")
            
            summary_lines.append("\nDetails for failed items (see log for more):")
            for i, res_item in enumerate(r for r in results if not r["success"]):
                if i >= 5: summary_lines.append(f"    (... and {failed_individual_liveries_or_archives - 5} more errors.)"); break
                err_detail = res_item['detail']; short_err = (err_detail[:120] + '...') if len(err_detail) > 120 else err_detail
                summary_lines.append(f" - '{Path(res_item['file']).name}': {short_err}")
            log_level_for_summary_msg = "ERROR"; messagebox_func = messagebox.showerror

        final_summary_msg = "\n".join(summary_lines)
        self.log(f"FINAL BATCH SUMMARY:\n{final_summary_msg}", log_level_for_summary_msg)
        messagebox_func(title, final_summary_msg)

    def on_close(self):
        self.log("Saving configuration on exit...", "DETAIL")
        try:
            self.save_config()
        except Exception as e:
            self.log(f"Error saving configuration during exit: {e}", "WARNING")
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
            try: 
                PROCESS_PER_MONITOR_DPI_AWARE = 2
                windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
            except (AttributeError, OSError):
                try: windll.user32.SetProcessDPIAware()
                except: print("WARNING: Could not set DPI awareness.") # Minimal print on final fallback
    except: pass # Ignore all errors related to DPI awareness setting if ctypes or calls fail

    root = tk.Tk()
    app = PMDGLiveryInstaller(root)
    root.mainloop()

if __name__ == "__main__":
    main()

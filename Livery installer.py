import os
import sys
import zipfile
import shutil
import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import webbrowser
# Pillow is optional - removed image handling for simplicity unless needed later
# from PIL import Image, ImageTk, ImageDraw, ImageFont
import subprocess # Kept and now actively used!
from datetime import datetime
import struct # Not actively used in current logic, but kept from original
import binascii # Not actively used in current logic, but kept from original
import threading
import time # Adding time module which is used in the code

# --- Constants ---
CONFIG_DIR_NAME = ".pmdg_livery_installer"
CONFIG_FILE_NAME = "config.json"
DEFAULT_MIN_GAME_VERSION = "1.37.19" # Update as needed for MSFS version compatibility

# Base folder names in Community (Corrected names with two '7's)
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
# Using a set for efficient lookup
EXPECTED_PMDG_PACKAGE_NAMES = {
    "pmdg-aircraft-77er",
    "pmdg-aircraft-77w",
    "pmdg-aircraft-77f",
    # Add other PMDG aircraft package names here if needed in the future
    "pmdg-aircraft-737-600",
    "pmdg-aircraft-737-700",
    "pmdg-aircraft-737-800",
    "pmdg-aircraft-737-900",
}


# --- Main Application Class ---
class PMDGLiveryInstaller:
    def __init__(self, master):
        self.master = master
        # Define app version attribute *early*
        self.app_version = "v1.8.5" # <<< Version bump reflecting ATC_ID.ini Handling

        master.title(f"PMDG 777 Livery Installer {self.app_version}") # Use version in title
        master.geometry("850x850") # Even taller for new config options
        master.minsize(750, 750)

        # --- Set Window Icon ---
        # Use raw string (r"...") or double backslashes for Windows paths
        icon_path = r"C:\Users\semar\Downloads\1d48b858-7443-43a4-9072-46a1a14b7b0f.ico"
        try:
            # Check if the file exists before trying to set it
            if os.path.exists(icon_path):
                master.iconbitmap(icon_path)
            else:
                print(f"Warning: Icon file not found at {icon_path}") # Log to console if icon missing
        except tk.TclError as e:
             print(f"Warning: Could not set window icon ({icon_path}): {e}") # Log error if Tkinter fails
        except Exception as e:
             print(f"Warning: Unexpected error setting icon: {e}")

        # Internal storage for selected zip files
        self.selected_zip_files = []

        # Configure colors
        self.bg_color = "#f0f0f0"
        self.header_bg = "#1a3f5c"
        self.header_fg = "white"
        self.button_color = "#2c5f8a"
        self.button_hover = "#3d7ab3"
        self.accent_color = "#007acc"
        self.success_color = "dark green"
        self.warning_color = "orange"
        self.error_color = "red"

        # Set styles
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

        # Create main container
        main_container = ttk.Frame(master, style="TFrame")
        main_container.pack(fill=tk.BOTH, expand=True)

        # Create header
        header_frame = ttk.Frame(main_container, style="Header.TFrame")
        header_frame.pack(fill=tk.X)

        # App title in header
        title_frame = ttk.Frame(header_frame, style="Header.TFrame")
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)

        header = ttk.Label(title_frame, text="PMDG 777 Livery Installation Tool", style="Header.TLabel")
        header.pack(side=tk.TOP, anchor=tk.W)

        sub_header = ttk.Label(title_frame,
                               text="Install custom liveries and generate layout for PMDG 777", # English
                               foreground="light gray", background=self.header_bg, font=("Arial", 10))
        sub_header.pack(side=tk.TOP, anchor=tk.W, pady=(0, 5))

        # Create main frame with padding
        self.main_frame = ttk.Frame(main_container, padding="20", style="TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.main_frame, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Setup tab
        setup_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(setup_tab, text="  Configuration  ") # English

        # Installation tab
        install_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(install_tab, text="  Install Livery(s)  ") # English

        # Help tab
        help_tab = ttk.Frame(self.notebook, padding=15, style="TFrame")
        self.notebook.add(help_tab, text="  Help  ") # English

        # Setup the UI components in each tab
        self._setup_setup_tab(setup_tab)
        self._setup_install_tab(install_tab)
        self._setup_help_tab(help_tab)

        # Status bar at the bottom
        status_frame = ttk.Frame(main_container, relief=tk.SUNKEN, borderwidth=1)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready") # English
        status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W, background='')
        status_label.pack(side=tk.LEFT, padx=10, pady=3)

        version_label = ttk.Label(status_frame, text=self.app_version, style="Status.TLabel", anchor=tk.E, background='')
        version_label.pack(side=tk.RIGHT, padx=10, pady=3)

        # Try to load previous paths from config file
        self.load_config()

        # Add a window close handler
        master.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_setup_tab(self, parent):
        """Set up the Setup tab with configuration options"""
        parent.columnconfigure(1, weight=1) # Make entry expand

        # Title
        ttk.Label(parent, text="Configuration Settings", style="Subheader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15)) # English

        # Community folder selection
        ttk.Label(parent, text="MSFS Community Folder:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.community_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.community_path_var, width=60).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Button(parent, text="Browse...", command=self.select_community_folder).grid(row=1, column=2, padx=5, pady=5) # English

        # Help text for community folder
        ttk.Label(parent, text="Location of your MSFS add-ons (Community folder).",
                  style="Info.TLabel").grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=5) # English

        # Common locations button
        ttk.Button(parent, text="Find Common Locations",
                   command=self.show_common_locations).grid(row=2, column=0, sticky=tk.W, padx=5) # English

        # --- PMDG Package Paths (LocalState) --- NEW SECTION ---
        pmdg_path_frame = ttk.LabelFrame(parent, text="PMDG Package Paths (for options.ini)", padding=10) # English
        pmdg_path_frame.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(20, 5))
        pmdg_path_frame.columnconfigure(1, weight=1)

        # 777-200ER Path
        ttk.Label(pmdg_path_frame, text="777-200ER Path:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.pmdg_77er_path_var = tk.StringVar()
        ttk.Entry(pmdg_path_frame, textvariable=self.pmdg_77er_path_var, width=55).grid(row=0, column=1, sticky=tk.EW, pady=5)
        ttk.Button(pmdg_path_frame, text="Browse...", command=lambda: self.select_pmdg_package_folder(self.pmdg_77er_path_var, "pmdg-aircraft-77er")).grid(row=0, column=2, padx=5, pady=5) # English

        # 777-300ER Path
        ttk.Label(pmdg_path_frame, text="777-300ER Path:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.pmdg_77w_path_var = tk.StringVar()
        ttk.Entry(pmdg_path_frame, textvariable=self.pmdg_77w_path_var, width=55).grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Button(pmdg_path_frame, text="Browse...", command=lambda: self.select_pmdg_package_folder(self.pmdg_77w_path_var, "pmdg-aircraft-77w")).grid(row=1, column=2, padx=5, pady=5) # English

        # 777F Path
        ttk.Label(pmdg_path_frame, text="777F Path:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.pmdg_77f_path_var = tk.StringVar()
        ttk.Entry(pmdg_path_frame, textvariable=self.pmdg_77f_path_var, width=55).grid(row=2, column=1, sticky=tk.EW, pady=5)
        ttk.Button(pmdg_path_frame, text="Browse...", command=lambda: self.select_pmdg_package_folder(self.pmdg_77f_path_var, "pmdg-aircraft-77f")).grid(row=2, column=2, padx=5, pady=5) # English

        # Info about PMDG LocalState path
        ttk.Label(pmdg_path_frame, text="Path to specific PMDG package folder (e.g., pmdg-aircraft-77er) inside '...\\LocalState\\packages'.",
                  style="Info.TLabel").grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=5, pady=(5,0)) # English


        # Layout generator selection
        ttk.Label(parent, text="MSFSLayoutGenerator.exe:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # Adjust row
        self.layout_generator_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.layout_generator_path_var, width=60).grid(row=4, column=1, sticky=tk.EW, pady=(20, 5)) # Adjust row
        ttk.Button(parent, text="Browse...", command=self.select_layout_generator).grid(row=4, column=2, padx=5, pady=(20, 5)) # English # Adjust row

        # Info about layout generator
        ttk.Label(parent, text="Tool used automatically to update layout.json.",
                  style="Info.TLabel").grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=5) # English # Adjust row

        # Download button for layout generator
        ttk.Button(parent, text="Download Tool",
                   command=lambda: webbrowser.open("https://github.com/HughesMDflyer4/MSFSLayoutGenerator/releases")).grid(row=5, column=0, sticky=tk.W, padx=5) # English # Adjust row

        # Reference livery folder selection
        ttk.Label(parent, text="Reference 777 Livery Folder:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # English # Adjust row
        self.reference_path_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.reference_path_var, width=60).grid(row=6, column=1, sticky=tk.EW, pady=(20, 5)) # Adjust row
        ttk.Button(parent, text="Browse...", command=self.select_reference_folder).grid(row=6, column=2, padx=5, pady=(20, 5)) # English # Adjust row

        # Info about reference livery
        ttk.Label(parent, text="Any installed PMDG 777 livery folder (used for manifest/layout templates).", # English
                  style="Info.TLabel").grid(row=7, column=1, columnspan=2, sticky=tk.W, padx=5) # Adjust row

        # --- Add Separator ---
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=8, column=0, columnspan=3, sticky=tk.EW, pady=25) # Adjust row

        # Save button
        save_btn = ttk.Button(parent, text="Save Configuration", command=self.save_config) # English
        save_btn.grid(row=9, column=0, columnspan=3, pady=10) # Adjust row


    def _setup_install_tab(self, parent):
        """Set up the Installation tab"""
        parent.columnconfigure(1, weight=1) # Make entry expand
        parent.rowconfigure(8, weight=1) # Make log expand (adjust row index)

        # Title
        ttk.Label(parent, text="Install New Livery(s)", style="Subheader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15)) # English

        # Livery zip selection
        ttk.Label(parent, text="Livery Archive(s):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # English
        self.livery_zip_display_var = tk.StringVar() # Variable for the Entry display
        self.livery_zip_entry = ttk.Entry(parent, textvariable=self.livery_zip_display_var, width=60, state='readonly') # Readonly display
        self.livery_zip_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)
        ttk.Button(parent, text="Browse...", command=self.select_livery_zip).grid(row=1, column=2, padx=5, pady=5) # English


        # Info about livery zip
        ttk.Label(parent, text="Select one or more ZIP files. (RAR/PTP not supported)", # English
                  style="Info.TLabel").grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(parent, text="IMPORTANT! If selecting multiple, they MUST be for the SAME aircraft variant.", # English
                   style="Warn.Info.TLabel").grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=5) # New warning label

        # Aircraft variant selection
        ttk.Label(parent, text="Aircraft Variant:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # English (Adjust row index)
        self.aircraft_variant_var = tk.StringVar()
        # self.aircraft_variant_var.set("300ER") # <<< REMOVED: No default selection

        variant_frame = ttk.Frame(parent, style="TFrame") # Apply style
        variant_frame.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=(20, 5)) # Adjust row index

        ttk.Radiobutton(variant_frame, text="777-200ER", variable=self.aircraft_variant_var, value="200ER").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(variant_frame, text="777-300ER", variable=self.aircraft_variant_var, value="300ER").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(variant_frame, text="777F", variable=self.aircraft_variant_var, value="F").pack(side=tk.LEFT)
        # Info text for variant selection
        ttk.Label(parent, text="You must select a variant.", style="Info.TLabel").grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=5) # English (Adjust row index)


        # Custom livery name option
        ttk.Label(parent, text="Livery Name (in sim):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=(20, 5)) # English (Adjust row index)
        self.custom_name_var = tk.StringVar()
        self.custom_name_entry = ttk.Entry(parent, textvariable=self.custom_name_var, width=60) # Store entry widget
        self.custom_name_entry.grid(row=6, column=1, sticky=tk.EW, pady=(20, 5)) # Adjust row index

        # Info about custom name
        ttk.Label(parent, text="Optional. Ignored if multiple files are selected (will auto-detect).", # English
                  style="Info.TLabel").grid(row=7, column=1, columnspan=2, sticky=tk.W, padx=5) # Adjust row index

        # --- Add Separator ---
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=8, column=0, columnspan=3, sticky=tk.EW, pady=25) # Adjust row index


        # Install button, progress bar, log frame container
        action_frame = ttk.Frame(parent, style="TFrame") # Apply style
        action_frame.grid(row=9, column=0, columnspan=3, sticky=tk.NSEW, pady=10) # Adjust row index
        action_frame.columnconfigure(0, weight=1)
        action_frame.rowconfigure(2, weight=1) # Make log expand within this frame

        # Install button with more prominence
        self.install_button = ttk.Button(action_frame, text="Install Livery(s) & Generate Layout", command=self.start_install_thread, style="Accent.TButton") # English
        self.install_button.grid(row=0, column=0, pady=(0, 15)) # Spans columns within its frame

        # Progress bar
        progress_frame = ttk.Frame(action_frame, style="TFrame") # Apply style
        progress_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        progress_frame.columnconfigure(1, weight=1)

        ttk.Label(progress_frame, text="Progress:").grid(row=0, column=0, sticky=tk.W) # English
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, style="Horizontal.TProgressbar")
        self.progress.grid(row=0, column=1, sticky=tk.EW, padx=5)

        # Log frame with a border
        log_frame = ttk.LabelFrame(action_frame, text="Installation Log", style="TLabelframe") # English
        log_frame.grid(row=2, column=0, sticky=tk.NSEW) # Spans columns within its frame
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        # Log text
        self.log_text = tk.Text(log_frame, height=12, width=80, wrap=tk.WORD, bd=0, font=("Courier New", 9), relief=tk.FLAT, background="white") # Use Courier for logs, set background
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Add a scrollbar to the log
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=(0, 5), pady=5)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Configure log tags
        self.log_text.tag_configure("INFO", foreground="black")
        self.log_text.tag_configure("SUCCESS", foreground=self.success_color)
        self.log_text.tag_configure("WARNING", foreground=self.warning_color)
        self.log_text.tag_configure("ERROR", foreground=self.error_color, font=("Courier New", 9, "bold"))
        self.log_text.tag_configure("STEP", foreground=self.header_bg, font=("Courier New", 9, "bold"))
        self.log_text.tag_configure("DETAIL", foreground="#555555")
        self.log_text.tag_configure("CMD", foreground="purple", font=("Courier New", 9, "italic"))
        # Make log initially read-only
        self.log_text.config(state=tk.DISABLED)


    def _setup_help_tab(self, parent):
        """Set up the Help tab with instructions"""
        # Create a scrollable frame for help content
        help_canvas = tk.Canvas(parent, highlightthickness=0, background=self.bg_color)
        help_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=help_canvas.yview)
        scrollable_frame = ttk.Frame(help_canvas, style="TFrame") # Apply style

        scrollable_frame.bind(
            "<Configure>",
            lambda e: help_canvas.configure(scrollregion=help_canvas.bbox("all")) # Removed width setting here
        )

        canvas_window = help_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        help_canvas.configure(yscrollcommand=help_scrollbar.set)

        # Adjust canvas window width when canvas resizes
        help_canvas.bind('<Configure>', lambda e: help_canvas.itemconfig(canvas_window, width=e.width))

        help_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        help_scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)

        # --- Help content ---
        current_row = 0
        initial_width = parent.winfo_reqwidth() # Get initial requested width
        wrap_len = max(500, initial_width - 80) # Estimate usable width

        def add_section_header(text):
            nonlocal current_row
            ttk.Label(scrollable_frame, text=text, style="Subheader.TLabel").grid(row=current_row, column=0, sticky="w", pady=(15, 5))
            current_row += 1

        def add_text(text, indent=0, style="TLabel"):
            nonlocal current_row, wrap_len
            ttk.Label(scrollable_frame, text=text, justify=tk.LEFT, wraplength=wrap_len, style=style).grid(row=current_row, column=0, sticky="w", padx=(indent * 20, 0))
            current_row += 1

        def add_bold_text(text, indent=0):
            nonlocal current_row, wrap_len
            ttk.Label(scrollable_frame, text=text, justify=tk.LEFT, font=("Arial", 10, "bold"), wraplength=wrap_len).grid(row=current_row, column=0, sticky="w", padx=(indent * 20, 0), pady=(5,0))
            current_row += 1

        # --- Quick Start ---
        add_section_header("Quick Start Guide") # English
        add_text("1. Go to the Configuration tab:") # English
        add_text("- Select your MSFS Community folder.", indent=1) # English
        add_text("- Set the 'PMDG Package Path' for each 777 variant you own (important for options.ini). Point it to the specific PMDG folder (e.g., pmdg-aircraft-77er) inside ...\\LocalState\\packages.", indent=1) # English
        add_text("- Select the MSFSLayoutGenerator.exe tool (download if needed).", indent=1) # English
        add_text("- Select any existing PMDG 777 livery folder as a Reference.", indent=1) # English
        add_text("- Click Save Configuration.", indent=1) # English
        add_text("2. Go to the Install Livery(s) tab:") # English
        add_text("- Browse for the livery archive file(s) (ZIP only).", indent=1) # English
        add_text("- IMPORTANT! Choose the correct Aircraft Variant (777-200ER, 777-300ER, or 777F). This is mandatory!", indent=1) # English
        add_text("- If selecting multiple ZIP files, ensure ALL are for the same variant you chose.", indent=1) # English
        add_text("- Optionally, enter a Livery Name if you selected only ONE file.", indent=1) # English
        add_text("- Click 'Install Livery(s) & Generate Layout'.", indent=1) # English
        add_text("3. Check the log for success or errors. The tool will attempt to run MSFSLayoutGenerator and copy/rename options.ini automatically.", indent=1) # English
        add_text("4. Launch MSFS and find your new livery/liveries! (Restart MSFS if it was running).", indent=1) # English


        # --- Configuration ---
        add_section_header("Configuration Details") # English
        add_bold_text("MSFS Community Folder:") # English
        add_text("This is where MSFS add-ons are installed.", indent=1) # English
        add_bold_text("PMDG Package Paths (LocalState):") # English
        add_text("Path to the specific PMDG aircraft package folder (e.g., 'pmdg-aircraft-77er', 'pmdg-aircraft-77w') inside the 'packages' folder within your MSFS LocalState.", indent=1) # English
        add_text("Used to copy the renamed '.ini' files (formerly options.ini). Set the path for each variant you own.", indent=1) # English
        add_text("- Store (Typical): %LOCALAPPDATA%\\Packages\\Microsoft.FlightSimulator_...\\LocalState\\packages\\pmdg-aircraft-77er", indent=2) # English
        add_text("- Steam (May vary): Look for the 'packages' folder within AppData\\Roaming, then the specific PMDG folder.", indent=2) # English
        add_text("Use the 'Browse...' button to select the folder containing 'work', 'SimObjects', etc.", indent=1) # English
        add_bold_text("MSFSLayoutGenerator.exe:")
        add_text("Required tool for automatically updating the layout.json file.", indent=1) # English
        add_text("Download: https://github.com/HughesMDflyer4/MSFSLayoutGenerator/releases", indent=1)
        add_bold_text("Reference 777 Livery Folder:") # English
        add_text("Needed to copy template manifest.json and layout.json files.", indent=1) # English
        add_text("Select the main folder of any correctly installed PMDG 777 livery.", indent=1) # English


        # --- Troubleshooting ---
        add_section_header("Troubleshooting") # English
        add_bold_text("Livery Not Showing in MSFS:") # English
        add_text("- Check the Installation Log for ERROR messages, especially during 'Generating layout.json' or 'Processing options.ini' steps.", indent=1) # English
        add_text("- Verify the Community Folder path is correct in Configuration.", indent=1) # English
        add_text("- Verify the MSFSLayoutGenerator.exe path is correct in Configuration.", indent=1) # English
        add_text("- Ensure you selected the correct Aircraft Variant during installation.", indent=1) # English
        add_text("- For 777-200ER, check the log if the correct engine type (GE/RR/PW) was detected and applied to aircraft.cfg.", indent=1) # English
        add_text("- Verify the 'PMDG Package Path (LocalState)' for the relevant variant is correct if you expected an .ini file to be copied.", indent=1) # English
        add_text("- Restart MSFS. Sometimes a restart is needed.", indent=1) # English
        add_text("- Check the MSFS Content Manager for the livery package.", indent=1) # English
        add_text("- If layout generation failed, you might need to run MSFSLayoutGenerator.exe manually.", indent=1) # English
        add_bold_text("Installation Errors:") # English
        add_text("- Ensure the ZIP archive(s) are not corrupted and contain expected folders (texture.*, model, aircraft.cfg, optionally options.ini or <atc_id>.ini).", indent=1) # English Updated
        add_text("- Verify the Reference Livery Folder selected is valid and working.", indent=1) # English
        add_text("- Check that MSFSLayoutGenerator.exe path is correct and the tool is functional.", indent=1) # English
        add_bold_text("Nested ZIPs:") # English
        add_text("- The tool attempts to detect and install liveries inside nested ZIP files (e.g., a 'pack' zip containing individual livery zips).", indent=1) # English
        add_text("- Check the log if a 'pack' file fails; it might indicate an unexpected internal structure.", indent=1) # English
        add_bold_text("RAR / PTP Files:") # English
        add_text("- This tool only supports ZIP archives.", indent=1) # English
        add_text("- PTP is PMDG's format; installation via PMDG Operations Center is recommended.", indent=1) # English


        # --- About ---
        add_section_header("About") # English
        add_text(f"PMDG 777 Livery Installer {self.app_version}")
        add_text("This tool prepares, copies, and configures livery files for the PMDG 777 family in MSFS.", style="TLabel") # English
        add_text("It handles folder creation, file extraction (ZIP, including nested), aircraft.cfg modification, options.ini/<atc_id>.ini handling, and automatically runs MSFSLayoutGenerator.exe.", style="TLabel") # English Updated
        add_text("Disclaimer: Use at your own risk. Not affiliated with PMDG or Microsoft.", style="Info.TLabel") # English

    def show_common_locations(self):
        """Show a dialog with common Community folder locations"""
        common_locations = """Common MSFS Community folder locations:

NOTE: [YourUsername] should be replaced with your actual Windows username.

Microsoft Store Version:
C:\\Users\\[YourUsername]\\AppData\\Local\\Packages\\Microsoft.FlightSimulator_8wekyb3d8bbwe\\LocalCache\\Packages\\Community

Steam Version:
C:\\Users\\[YourUsername]\\AppData\\Roaming\\Microsoft Flight Simulator\\Packages\\Community

Custom Installation Drive (Example D:):
D:\\MSFS\\Community (If you chose a custom path during MSFS installation)

Xbox App / Game Pass PC (May Vary):
Look in drive settings under Xbox app, often involves hidden/protected folders like 'WpSystem' or 'WindowsApps'. Access might be restricted. Using the Store/Steam version path is more common for PC users.

Finding AppData:
Press Windows Key + R, type `%appdata%` and press Enter to open the Roaming folder.
Press Windows Key + R, type `%localappdata%` and press Enter to open the Local folder.
""" # English content

        location_window = tk.Toplevel(self.master)
        location_window.title("Common Community Folder Locations") # English
        location_window.geometry("700x400")
        location_window.resizable(False, False)
        location_window.transient(self.master) # Make it modal relative to the main window
        location_window.grab_set() # Grab focus

        # Use themed frame for consistent background
        win_frame = ttk.Frame(location_window, padding=10, style="TFrame")
        win_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(win_frame, wrap=tk.WORD, padx=15, pady=15, bd=0, relief=tk.FLAT, font=("Arial", 10), background=self.bg_color) # Match background
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, common_locations)
        text_widget.config(state=tk.DISABLED) # Make read-only

        btn_frame = ttk.Frame(win_frame, padding=(0, 10, 0, 0), style="TFrame") # Padding top only
        btn_frame.pack(fill=tk.X)

        copy_btn = ttk.Button(btn_frame, text="Copy Info to Clipboard", # English
                              command=lambda: self.copy_to_clipboard(common_locations, location_window))
        copy_btn.pack(side=tk.LEFT, padx=5)

        close_btn = ttk.Button(btn_frame, text="Close", command=location_window.destroy) # English
        close_btn.pack(side=tk.RIGHT, padx=5)

        # Center the popup window
        location_window.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (location_window.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (location_window.winfo_height() // 2)
        location_window.geometry(f'+{x}+{y}')


    def copy_to_clipboard(self, text, parent_window):
        """Copies text to clipboard and shows feedback."""
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(text)
            self.master.update() # Required on some platforms
            messagebox.showinfo("Copied", "Locations copied to clipboard.", parent=parent_window) # English
        except tk.TclError:
             messagebox.showwarning("Clipboard Error", "Could not access the clipboard.", parent=parent_window) # English


    def log(self, message, level="INFO"):
        """Add a message to the log display with appropriate tag"""
        # Ensure this runs on the main thread
        if threading.current_thread() is not threading.main_thread():
            self.master.after(0, self.log, message, level)
            return

        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            prefix = f"[{timestamp}] [{level.upper()}] "
            tag = level.upper() if level.upper() in ["SUCCESS", "WARNING", "ERROR", "STEP", "DETAIL", "CMD"] else "INFO"

            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, prefix + message + "\n", tag)
            self.log_text.config(state=tk.DISABLED)
            self.log_text.see(tk.END) # Scroll to the end
        except Exception as e:
            print(f"Error logging message: {e}") # Fallback print


    def select_community_folder(self):
        initial_dir = self.community_path_var.get() if os.path.isdir(self.community_path_var.get()) else str(Path.home())
        folder = filedialog.askdirectory(title="Select MSFS Community Folder", initialdir=initial_dir) # English
        if folder:
            self.community_path_var.set(folder)
            self.log(f"Community folder selected: {folder}", "DETAIL") # English

    def _get_parent_localstate_packages_path(self) -> Path | None:
        """Tries to find the parent 'packages' folder inside LocalState."""
        try:
            local_app_data = os.getenv('LOCALAPPDATA')
            if not local_app_data: return None
            packages_dir = Path(local_app_data) / "Packages"
            if not packages_dir.is_dir(): return None

            msfs_pkg_pattern = "Microsoft.FlightSimulator_*_8wekyb3d8bbwe"
            for item in packages_dir.iterdir():
                if item.is_dir() and re.match(msfs_pkg_pattern, item.name, re.IGNORECASE):
                    potential_path = item / "LocalState" / "packages"
                    if potential_path.is_dir():
                        return potential_path # Return the parent 'packages' path
            # Check Steam default location (less reliable)
            app_data = os.getenv('APPDATA')
            if app_data:
                steam_path = Path(app_data) / "Microsoft Flight Simulator" / "Packages"
                if steam_path.is_dir():
                    # This is the Community/Official path, LocalState might be elsewhere
                    # For Steam, LocalState is often harder to pinpoint reliably without user input
                    pass

        except Exception:
            pass # Ignore errors during auto-detect
        return None

    def select_pmdg_package_folder(self, target_var: tk.StringVar, expected_folder_prefix: str):
        """Select the specific PMDG package folder inside LocalState/packages."""
        # Try to start browsing from the parent 'packages' folder if possible
        initial_dir_guess = self._get_parent_localstate_packages_path()
        if not initial_dir_guess or not initial_dir_guess.is_dir():
            # Fallback if parent couldn't be found
             local_app_data = os.getenv('LOCALAPPDATA')
             initial_dir_guess = Path(local_app_data) / 'Packages' if local_app_data else Path.home()

        folder = filedialog.askdirectory(
            title=f"Select PMDG Package Folder (e.g., {expected_folder_prefix}) in ...LocalState\\packages", # English
            initialdir=str(initial_dir_guess) # Start in parent 'packages' or fallback
        )
        if folder:
            p_folder = Path(folder)
            folder_name_lower = p_folder.name.lower()
            # Validate if the selected folder name is one of the expected PMDG package names
            if folder_name_lower in EXPECTED_PMDG_PACKAGE_NAMES:
                 # Additionally check if it matches the specific type expected for this field
                 if folder_name_lower == expected_folder_prefix.lower():
                    # Check if it seems to be inside a 'packages' folder for extra safety
                    if p_folder.parent.name.lower() == 'packages':
                        target_var.set(str(p_folder))
                        self.log(f"PMDG Package Path ({expected_folder_prefix}) set: {p_folder}", "DETAIL") # English
                    else:
                        # Warn if not inside 'packages', but allow it
                        messagebox.showwarning("Possible Incorrect Path", f"The selected folder '{p_folder.name}' is a valid PMDG package, but it doesn't seem to be inside a folder named 'packages'.\n\nPlease ensure this is the correct path within LocalState.") # English
                        target_var.set(str(p_folder))
                        self.log(f"PMDG Package Path ({expected_folder_prefix}) set (Warning: not in 'packages'): {p_folder}", "WARNING") # English
                 else:
                     # Correct PMDG package type, but wrong variant selected
                     messagebox.showerror("Incorrect Variant", f"You selected the folder '{p_folder.name}', but expected a folder like '{expected_folder_prefix}'.\n\nPlease select the correct PMDG package folder for this aircraft variant.") # English
                     self.log(f"Incorrect PMDG package variant selected for {expected_folder_prefix}. Selected: {folder}", "ERROR") # English
            else:
                messagebox.showerror("Invalid Folder", f"The selected folder '{p_folder.name}' does not appear to be a valid PMDG package folder (e.g., {expected_folder_prefix}, etc.).\n\nPlease select the correct folder inside '...\\LocalState\\packages'.") # English
                self.log(f"Invalid PMDG Package Path selected: {folder}", "ERROR") # English


    def select_layout_generator(self):
        initial_dir = os.path.dirname(self.layout_generator_path_var.get()) if self.layout_generator_path_var.get() else str(Path.home())
        file = filedialog.askopenfilename(
            title="Select MSFSLayoutGenerator.exe", # English
            filetypes=[("Executable files", "*.exe")], # English
            initialdir=initial_dir
            )
        if file:
            self.layout_generator_path_var.set(file)
            self.log(f"Layout generator selected: {file}", "DETAIL") # English


    def select_reference_folder(self):
        initial_dir = self.community_path_var.get() if os.path.isdir(self.community_path_var.get()) else str(Path.home())
        folder = filedialog.askdirectory(
            title="Select Reference PMDG 777 Livery Folder", # English
            initialdir=initial_dir
            )
        if folder:
            manifest_path = Path(folder) / "manifest.json"
            layout_path = Path(folder) / "layout.json"
            if manifest_path.is_file() and layout_path.is_file():
                self.reference_path_var.set(folder)
                self.log(f"Reference livery folder selected: {folder}", "DETAIL") # English
            else:
                missing = []
                if not manifest_path.is_file(): missing.append("manifest.json")
                if not layout_path.is_file(): missing.append("layout.json")
                messagebox.showwarning("Invalid Reference", f"The selected folder is missing required file(s): {', '.join(missing)}. Please select a valid PMDG livery folder.") # English
                self.log(f"Invalid reference folder selected (missing {', '.join(missing)}): {folder}", "WARNING") # English


    def select_livery_zip(self):
        """Allows selecting one or multiple zip files."""
        initial_dir = str(Path.home() / "Downloads") if os.path.exists(str(Path.home() / "Downloads")) else str(Path.home())
        files = filedialog.askopenfilenames(
            title="Select Livery Archive File(s) (.zip)", # English
            filetypes=[
                ("Supported ZIP Archives", "*.zip"), # English
                ("All files", "*.*")
            ],
            initialdir=initial_dir
        )
        if files: # files is a tuple of paths
            self.selected_zip_files = list(files) # Store the list internally
            num_files = len(self.selected_zip_files)
            if num_files == 1:
                display_text = os.path.basename(self.selected_zip_files[0])
                self.custom_name_entry.config(state=tk.NORMAL) # Enable custom name for single file
                self.log(f"Livery archive selected: {display_text}", "DETAIL") # English
                if not self.custom_name_var.get():
                    base_name = os.path.splitext(display_text)[0]
                    clean_name = re.sub(r'^(pmdg[-_]?)?(777[-_]?(200er|300er|f|w)?[-_]?)?', '', base_name, flags=re.IGNORECASE).strip('-_ ')
                    clean_name = re.sub(r'[-_]+', ' ', clean_name)
                    clean_name = re.sub(r'\s+', ' ', clean_name)
                    clean_name = ' '.join(word.capitalize() for word in clean_name.split())
                    if clean_name:
                        self.custom_name_var.set(clean_name)
                        self.log(f"Suggested livery name: {clean_name}", "DETAIL") # English
            else:
                display_text = f"[{num_files} files selected]" # English
                self.custom_name_var.set("") # Clear custom name field
                self.custom_name_entry.config(state=tk.DISABLED) # Disable custom name for multiple files
                self.log(f"{num_files} livery archives selected.", "INFO") # English

            self.livery_zip_display_var.set(display_text) # Update the entry display
        else:
            self.selected_zip_files = []
            self.livery_zip_display_var.set("")
            self.custom_name_entry.config(state=tk.NORMAL) # Re-enable if previously disabled
            self.log("Livery archive selection cancelled.", "DETAIL") # English


    def save_config(self):
        """Save configuration to a file"""
        config = {
            "community_path": self.community_path_var.get(),
            "layout_generator_path": self.layout_generator_path_var.get(),
            "reference_path": self.reference_path_var.get(),
            "pmdg_77er_path": self.pmdg_77er_path_var.get(), # <<< SAVE NEW VARS
            "pmdg_77w_path": self.pmdg_77w_path_var.get(),
            "pmdg_77f_path": self.pmdg_77f_path_var.get()
        }
        try:
            config_dir = Path.home() / CONFIG_DIR_NAME
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / CONFIG_FILE_NAME
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            self.log("Configuration saved successfully.", "SUCCESS") # English
            self.status_var.set("Configuration saved") # English
            self.master.after(2000, lambda: self.status_var.set("Ready")) # Reset status after 2s
        except Exception as e:
            self.log(f"Error saving configuration: {str(e)}", "ERROR") # English
            messagebox.showerror("Configuration Error", f"Could not save configuration:\n{e}") # English


    def load_config(self):
        """Load configuration from a file"""
        try:
            config_path = Path.home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME
            if config_path.exists():
                with open(config_path, "r", encoding='utf-8') as f:
                    config = json.load(f)
                self.community_path_var.set(config.get("community_path", ""))
                self.layout_generator_path_var.set(config.get("layout_generator_path", ""))
                self.reference_path_var.set(config.get("reference_path", ""))
                self.pmdg_77er_path_var.set(config.get("pmdg_77er_path", "")) # <<< LOAD NEW VARS
                self.pmdg_77w_path_var.set(config.get("pmdg_77w_path", ""))
                self.pmdg_77f_path_var.set(config.get("pmdg_77f_path", ""))
                self.log("Configuration loaded.", "INFO") # English
            else:
                self.log("No configuration file found. Please configure paths in the Configuration tab.", "INFO") # English

        except json.JSONDecodeError as e:
            self.log(f"Error decoding configuration file: {str(e)}. Please check or delete the config file.", "ERROR") # English
            messagebox.showerror("Configuration Error", f"Could not load configuration file (invalid JSON):\n{config_path}\nError: {e}") # English
        except Exception as e:
            self.log(f"Error loading configuration: {str(e)}", "WARNING") # English


    def get_livery_name(self, archive_path, temp_extract_dir):
        """
        Determine the livery name for a SINGLE archive.
        Priority: aircraft.cfg title > archive filename.
        """
        try:
            cfg_path = self.find_file_in_dir(temp_extract_dir, "aircraft.cfg")
            if cfg_path and os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as cfg_file:
                    content = cfg_file.read()
                    fltsim_match = re.search(r'\[FLTSIM\.0\].*?title\s*=\s*"(.*?)"',
                                             content, re.DOTALL | re.IGNORECASE)
                    if fltsim_match:
                        title_name = fltsim_match.group(1).strip()
                        if title_name:
                            self.log(f"Detected name from aircraft.cfg [FLTSIM.0]: {title_name}", "INFO") # English
                            return title_name

                    simple_match = re.search(r'^\s*title\s*=\s*"(.*?)"', content, re.MULTILINE | re.IGNORECASE)
                    if simple_match:
                        title_name = simple_match.group(1).strip()
                        if title_name:
                            self.log(f"Detected name from aircraft.cfg (fallback): {title_name}", "INFO") # English
                            return title_name
            else:
                self.log("aircraft.cfg not found in archive for name detection.", "DETAIL") # English
        except Exception as e:
            self.log(f"Could not read aircraft.cfg for name detection: {e}", "WARNING") # English

        # Fallback to cleaned archive filename
        default_name = os.path.splitext(os.path.basename(str(archive_path)))[0]
        clean_name = re.sub(r'^(pmdg[-_]?)?(777[-_]?(200er|300er|f|w)?[-_]?)?', '', default_name, flags=re.IGNORECASE).strip('-_ ')
        clean_name = re.sub(r'[-_]+', ' ', clean_name)
        clean_name = re.sub(r'\s+', ' ', clean_name)
        clean_name = ' '.join(word.capitalize() for word in clean_name.split())
        if not clean_name: clean_name = "Unnamed Livery" # English
        self.log(f"Using cleaned filename as livery name: {clean_name}", "INFO") # English
        return clean_name

    def extract_atc_id(self, cfg_path: Path) -> str | None:
        """Extracts the atc_id value from the [fltsim.0] section of aircraft.cfg."""
        if not cfg_path.is_file():
            self.log(f"Cannot extract atc_id, file not found: {cfg_path}", "WARNING") # English
            return None
        try:
            with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # Find [fltsim.0] section then look for atc_id within it
            fltsim0_match = re.search(r'\[fltsim\.0\](.*?)(\n\[|$)', content, re.DOTALL | re.IGNORECASE)
            if fltsim0_match:
                section_content = fltsim0_match.group(1)
                # Regex allows optional quotes and captures alphanumeric, hyphen, underscore
                atc_id_match = re.search(r'^\s*atc_id\s*=\s*"?([a-zA-Z0-9_-]+)"?', section_content, re.MULTILINE | re.IGNORECASE)
                if atc_id_match:
                    atc_id = atc_id_match.group(1).strip()
                    if atc_id:
                        # Further sanitize ATC ID for filename safety
                        safe_atc_id = re.sub(r'[\\/*?:"<>|]', '_', atc_id)
                        if safe_atc_id != atc_id:
                             self.log(f"atc_id '{atc_id}' sanitized to '{safe_atc_id}' for filename.", "DETAIL") # English
                        if not safe_atc_id:
                             self.log(f"atc_id '{atc_id}' became empty after sanitization.", "WARNING") # English
                             return None
                        self.log(f"Found atc_id in [fltsim.0]: '{safe_atc_id}'", "DETAIL") # English
                        return safe_atc_id
                    else:
                        self.log("Found atc_id in [fltsim.0] but it is empty.", "WARNING") # English
                else:
                    self.log("atc_id not found within [fltsim.0].", "WARNING") # English
            else:
                self.log("[fltsim.0] section not found in aircraft.cfg.", "WARNING") # English
        except Exception as e:
            self.log(f"Error extracting atc_id from {cfg_path}: {e}", "ERROR") # English
        return None


    def verify_settings(self):
        """Verify that all required settings are valid before installation."""
        community_path = self.community_path_var.get()
        layout_generator = self.layout_generator_path_var.get()
        reference_path = self.reference_path_var.get()
        # Get all three PMDG paths
        pmdg_77er_path = self.pmdg_77er_path_var.get()
        pmdg_77w_path = self.pmdg_77w_path_var.get()
        pmdg_77f_path = self.pmdg_77f_path_var.get()
        livery_archives = self.selected_zip_files
        aircraft_variant = self.aircraft_variant_var.get()
        errors = []

        if not community_path: errors.append("- MSFS Community Folder path not set.") # English
        elif not os.path.isdir(community_path): errors.append(f"- Community Folder does not exist or is not a directory:\n  {community_path}") # English

        # <<< Check all three PMDG LocalState Package Paths >>>
        if not pmdg_77er_path: errors.append("- 777-200ER Package Path (LocalState) not set.") # English
        elif not os.path.isdir(pmdg_77er_path): errors.append(f"- 777-200ER Package Path (LocalState) not a valid directory:\n  {pmdg_77er_path}") # English
        elif not Path(pmdg_77er_path).name.lower() == "pmdg-aircraft-77er": errors.append(f"- 777-200ER Package Path folder name should be 'pmdg-aircraft-77er'.\n  Found: {Path(pmdg_77er_path).name}") # English

        if not pmdg_77w_path: errors.append("- 777-300ER Package Path (LocalState) not set.") # English
        elif not os.path.isdir(pmdg_77w_path): errors.append(f"- 777-300ER Package Path (LocalState) not a valid directory:\n  {pmdg_77w_path}") # English
        elif not Path(pmdg_77w_path).name.lower() == "pmdg-aircraft-77w": errors.append(f"- 777-300ER Package Path folder name should be 'pmdg-aircraft-77w'.\n  Found: {Path(pmdg_77w_path).name}") # English

        if not pmdg_77f_path: errors.append("- 777F Package Path (LocalState) not set.") # English
        elif not os.path.isdir(pmdg_77f_path): errors.append(f"- 777F Package Path (LocalState) not a valid directory:\n  {pmdg_77f_path}") # English
        elif not Path(pmdg_77f_path).name.lower() == "pmdg-aircraft-77f": errors.append(f"- 777F Package Path folder name should be 'pmdg-aircraft-77f'.\n  Found: {Path(pmdg_77f_path).name}") # English


        if not layout_generator: errors.append("- MSFSLayoutGenerator.exe path not set.") # English
        elif not os.path.isfile(layout_generator): errors.append(f"- MSFSLayoutGenerator.exe not found or not a file:\n  {layout_generator}") # English
        elif not layout_generator.lower().endswith(".exe"): errors.append(f"- MSFSLayoutGenerator path does not point to an .exe file:\n  {layout_generator}") # English
        if not reference_path: errors.append("- Reference Livery Folder path not set.") # English
        elif not os.path.isdir(reference_path): errors.append(f"- Reference Livery Folder does not exist or not a directory:\n  {reference_path}") # English
        elif not os.path.exists(os.path.join(reference_path, "manifest.json")): errors.append(f"- Reference Livery Folder missing manifest.json:\n  {reference_path}") # English
        elif not os.path.exists(os.path.join(reference_path, "layout.json")): errors.append(f"- Reference Livery Folder missing layout.json:\n  {reference_path}") # English

        if not aircraft_variant:
            errors.append("- You must select an Aircraft Variant.") # English

        if not livery_archives:
            errors.append("- No livery archive files (.zip) selected.") # English
        else:
            for archive_path in livery_archives:
                if not os.path.isfile(archive_path):
                    errors.append(f"- Selected livery archive file does not exist:\n  {archive_path}") # English
                elif not str(archive_path).lower().endswith(".zip"):
                     errors.append(f"- Selected file is not a supported format (.zip):\n  {archive_path}") # English

        return errors


    def find_file_in_dir(self, directory, filename_lower):
        """Recursively searches for a file (case-insensitive) in a directory."""
        search_path = Path(directory)
        for root, dirs, files in os.walk(search_path):
            # Optimization: Don't descend into known unrelated large folders if looking at top level
            # if Path(root) == search_path:
            #     dirs[:] = [d for d in dirs if d.lower() not in ['some_large_unrelated_folder']]

            for file in files:
                if file.lower() == filename_lower:
                    return os.path.join(root, file)
        return None

    def find_dir_in_dir(self, directory, dirname_lower):
        """Recursively searches for a directory (case-insensitive) in a directory."""
        search_dir = Path(directory)
        # Check top level first
        for item in search_dir.iterdir():
            if item.is_dir() and item.name.lower() == dirname_lower:
                return str(item)
        # Then search recursively
        for root, dirs, files in os.walk(search_dir, topdown=True):
            # Optimization: If we're searching for 'model', don't go into 'texture.*'
            if dirname_lower == 'model':
                 dirs[:] = [d for d in dirs if not d.lower().startswith('texture.')]
            elif dirname_lower.startswith('texture.'): # Searching for texture.xxx
                 dirs[:] = [d for d in dirs if d.lower() != 'model']


            for d in list(dirs): # Iterate over copy
                if d.lower() == dirname_lower:
                    found_path = Path(root) / d
                    if found_path.is_dir():
                        return str(found_path)
                    dirs.remove(d) # Don't descend further into this wrongly named item

        return None


    def find_texture_dirs_in_dir(self, directory):
        """Finds all directories starting with 'texture.' (case-insensitive)."""
        texture_dirs = []
        search_dir = Path(directory)
        # Check top level first
        try:
            for item in search_dir.iterdir():
                if item.is_dir() and item.name.lower().startswith("texture."):
                    if str(item) not in texture_dirs:
                        texture_dirs.append(str(item))
        except OSError as e:
             self.log(f"Error listing top-level directory {search_dir} for textures: {e}", "WARNING")

        # If not found at top level, search recursively (more thorough)
        if not texture_dirs:
            try:
                for root, dirs, files in os.walk(search_dir, topdown=True):
                    # Optimization: Don't descend into 'model' or already found texture dirs
                    dirs[:] = [d for d in dirs if d.lower() != 'model' and not d.lower().startswith('texture.')]

                    root_path = Path(root)
                    for d in list(dirs): # Use copy
                        if d.lower().startswith("texture."):
                            full_path = root_path / d
                            if full_path.is_dir():
                                if str(full_path) not in texture_dirs:
                                    texture_dirs.append(str(full_path))
                                dirs.remove(d) # Don't descend further
            except OSError as e:
                self.log(f"Error walking directory {search_dir} for textures: {e}", "WARNING")

        return texture_dirs


    def start_install_thread(self):
        """Validates settings and starts the installation in a separate thread."""
        errors = self.verify_settings()
        if errors:
            error_message = "Please fix the following configuration issues before installing:\n\n" + "\n".join(errors) # English
            messagebox.showerror("Configuration Errors", error_message) # English
            if any("Community" in e or "MSFSLayoutGenerator" in e or "Reference" in e or "LocalState" in e or "Package Path" in e for e in errors):
                self.notebook.select(0) # Select Setup tab (index 0)
            elif any("Aircraft Variant" in e or "livery archive" in e for e in errors):
                 self.notebook.select(1) # Select Install tab (index 1)
            return

        # Clear log and reset progress on main thread before starting thread
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Starting installation...") # English
        self.log("Starting installation process...", "STEP") # English
        self.install_button.config(state=tk.DISABLED) # Disable button during install

        # Get the list of files to install
        files_to_install = list(self.selected_zip_files) # Make a copy

        # Start the actual installation logic in a background thread
        install_thread = threading.Thread(target=self.install_livery_logic, args=(files_to_install,), daemon=True)
        install_thread.start()


    def _extract_archive(self, archive_path: Path, temp_dir: Path):
        """Extracts a single archive to the specified temp directory."""
        self.log(f"Extracting '{archive_path.name}' to {temp_dir}...", "INFO")
        if archive_path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    # Enhanced check for potentially problematic members
                    MAX_PATH_LEN = 500 # Arbitrary limit
                    for member_info in zip_ref.infolist():
                        member_path = member_info.filename
                        if member_path.startswith('/') or member_path.startswith('\\') or '..' in member_path:
                            raise ValueError(f"Archive contains potentially unsafe path: {member_path}")
                        if len(member_path) > MAX_PATH_LEN:
                             raise ValueError(f"Archive contains excessively long path: {member_path[:50]}...")
                    zip_ref.extractall(temp_dir)
                self.log(f"Archive '{archive_path.name}' extracted successfully.", "SUCCESS")
            except zipfile.BadZipFile:
                raise ValueError(f"Invalid or corrupted ZIP file: {archive_path.name}")
            except Exception as e:
                raise RuntimeError(f"Failed to extract ZIP file '{archive_path.name}': {e}")
        else:
            raise ValueError("Unsupported archive type. Only .zip files are supported.")

    def _is_nested_archive(self, directory: Path) -> bool:
        """
        Checks if the directory primarily contains other zip files.
        Improved heuristic: Checks inside single subfolder if present.
        Considers nested if zips exist AND (no textures OR few other files).
        """
        zip_count = 0
        other_file_folder_count = 0
        has_texture_folder = False
        check_dir = directory # Start with the main extraction dir

        try:
            items = list(check_dir.iterdir()) # Get items once
            # Handle case where zip extracts into a single subfolder
            if len(items) == 1 and items[0].is_dir() and not items[0].name.startswith('.'):
                 # Check inside this single subfolder instead
                 self.log(f"Checking single subfolder '{items[0].name}' for nested structure.", "DETAIL")
                 check_dir = items[0]

            # Now iterate through the effective directory contents
            for item in check_dir.iterdir():
                # Ignore hidden files/folders like __MACOSX often found in zips
                if item.name.startswith('.') or item.name == "__MACOSX":
                    continue
                if item.is_file() and item.suffix.lower() == '.zip':
                    zip_count += 1
                elif item.is_dir():
                    other_file_folder_count += 1
                    if item.name.lower().startswith('texture.'):
                        has_texture_folder = True
                elif item.is_file(): # Count other files like readme, jpg etc.
                    other_file_folder_count += 1

        except OSError as e:
            self.log(f"Error checking directory contents for nested zips: {e}", "WARNING")
            return False # Assume not nested if we can't check

        # Heuristic:
        # 1. If zip files exist AND there are NO texture folders at this level, assume nested.
        # 2. OR If zip files exist AND very few other files/folders (<=2 allows for readme/preview), assume nested.
        is_nested = (zip_count > 0 and not has_texture_folder) or \
                    (zip_count > 0 and other_file_folder_count <= 2)

        if is_nested:
            self.log(f"Detected nested structure in '{check_dir.name}'. Found {zip_count} zip(s), {other_file_folder_count} other items, has_texture={has_texture_folder}.", "INFO")
        # else: # Debugging log if needed
        #     self.log(f"Not detected as nested in '{check_dir.name}'. Zips:{zip_count}, Others:{other_file_folder_count}, Texture:{has_texture_folder}.", "DETAIL")

        return is_nested

    def _process_single_livery(self, extracted_livery_path: Path, livery_archive_path: Path, common_config: dict) -> tuple[bool, str]:
        """Processes a single extracted livery (can be called recursively for nested zips)."""
        livery_success = False
        ini_file_found = False # Track if we found options.ini OR <atc_id>.ini
        ini_processed_successfully = False # Track if the found ini was copied
        error_detail = "Unknown error during single livery processing."
        livery_name = "Unknown Livery" # Default

        try:
            # --- Step 2: Determine Livery Name ---
            livery_name = self.get_livery_name(livery_archive_path, extracted_livery_path)
            sanitized_livery_name = re.sub(r'[\\/*?:"<>|]', '_', livery_name)
            sanitized_livery_name = sanitized_livery_name.strip()
            if not sanitized_livery_name:
                sanitized_livery_name = f"Unnamed_{livery_archive_path.stem}" # Use stem of original zip if needed
                self.log("Livery name empty after sanitization, using filename-based name.", "WARNING")

            # --- Step 3: Define & Create Livery Specific Folders ---
            livery_simobjects_subfolder_name = f"{common_config['base_aircraft_folder_name']} {sanitized_livery_name}"
            livery_path = common_config['main_package_folder'] / "SimObjects" / "Airplanes" / livery_simobjects_subfolder_name
            self.log(f"Target livery folder: {livery_path}", "DETAIL")
            if livery_path.exists():
                self.log(f"Livery folder already exists. Overwriting contents.", "WARNING")
                try:
                    shutil.rmtree(livery_path)
                    self.log(f"Removed existing folder: {livery_path}", "DETAIL")
                    time.sleep(0.1)
                except OSError as e:
                    if sys.platform == "win32" and isinstance(e, PermissionError):
                         raise RuntimeError(f"Failed to remove existing folder '{livery_path}'. Ensure MSFS is closed.")
                    else:
                         raise RuntimeError(f"Failed to remove existing livery folder '{livery_path}': {e}.")
            livery_path.mkdir(parents=True, exist_ok=True)
            self.log("Created livery installation folders.", "SUCCESS")

            # --- Step 4: Manifest/Layout handled outside this function ---
            # Manifest and Layout are copied/updated once before the loop in install_livery_logic

            # --- Step 5: Find and Copy Livery Files ---
            self.log("Locating required files in extracted archive...", "INFO")
            aircraft_cfg_src = self.find_file_in_dir(extracted_livery_path, "aircraft.cfg")
            if not aircraft_cfg_src: raise FileNotFoundError("aircraft.cfg not found in extracted files.")
            self.log(f"Found aircraft.cfg: {os.path.relpath(aircraft_cfg_src, extracted_livery_path)}", "DETAIL")
            model_dir_src = self.find_dir_in_dir(extracted_livery_path, "model")
            if model_dir_src: self.log(f"Found model folder: {os.path.relpath(model_dir_src, extracted_livery_path)}", "DETAIL")
            else: self.log("Model folder not found (often OK).", "DETAIL")
            texture_dirs_src = self.find_texture_dirs_in_dir(extracted_livery_path)
            if not texture_dirs_src: raise FileNotFoundError("No 'texture.*' folders found in extracted files.")
            for tex_dir in texture_dirs_src: self.log(f"Found texture folder: {os.path.relpath(tex_dir, extracted_livery_path)}", "DETAIL")

            self.log("Copying livery files to installation folder...", "INFO")
            aircraft_cfg_dest = livery_path / "aircraft.cfg"
            try: shutil.copy2(aircraft_cfg_src, aircraft_cfg_dest)
            except Exception as e: raise RuntimeError(f"Failed to copy aircraft.cfg: {e}")
            if model_dir_src:
                model_dir_dest = livery_path / "model"
                try: shutil.copytree(model_dir_src, model_dir_dest, dirs_exist_ok=True)
                except Exception as e: raise RuntimeError(f"Failed to copy model folder: {e}")
            for tex_dir_src in texture_dirs_src:
                tex_name = Path(tex_dir_src).name
                tex_dir_dest = livery_path / tex_name
                try: shutil.copytree(tex_dir_src, tex_dir_dest, dirs_exist_ok=True)
                except Exception as e: raise RuntimeError(f"Failed to copy texture folder '{tex_name}': {e}")

            # Copy extras
            copied_extras = []
            cfg_parent_dir = Path(aircraft_cfg_src).parent
            try:
                for item in os.listdir(cfg_parent_dir):
                    item_src = cfg_parent_dir / item
                    # Exclude options.ini AND <atc_id>.ini from being copied here
                    atc_id_temp = self.extract_atc_id(aircraft_cfg_dest) # Get ATC ID again for this check
                    exclude_files = ["aircraft.cfg", "options.ini"]
                    if atc_id_temp:
                        exclude_files.append(f"{atc_id_temp}.ini")

                    if item_src.is_file() and item.name.lower() not in exclude_files:
                        ext = item_src.suffix.lower()
                        if ext in ['.json', '.ini', '.cfg', '.xml', '.dat', '.txt']:
                            item_dest = livery_path / item
                            try:
                                if not item_dest.exists():
                                    shutil.copy2(item_src, item_dest)
                                    copied_extras.append(item)
                            except Exception as e: self.log(f"Could not copy extra file '{item}': {e}", "WARNING")
                if copied_extras: self.log(f"Copied extra config files: {', '.join(copied_extras)}", "DETAIL")
            except Exception as e: self.log(f"Error scanning for extra files near aircraft.cfg: {e}", "WARNING")

            self.log("Finished copying essential livery files.", "SUCCESS")

            # --- Step 5.5: Process options.ini / <atc_id>.ini --- <<< UPDATED LOGIC >>>
            self.log("Searching for options.ini or <atc_id>.ini...", "INFO")
            atc_id = self.extract_atc_id(aircraft_cfg_dest) # Use the *copied* cfg path
            ini_file_to_copy_src = None
            new_ini_filename = None
            ini_source_type = None # 'options' or 'atc_id'

            if atc_id:
                new_ini_filename = f"{atc_id}.ini"
                # 1. Look for options.ini first
                options_ini_src_path = self.find_file_in_dir(extracted_livery_path, "options.ini")
                if options_ini_src_path:
                    self.log(f"Found options.ini at: {os.path.relpath(options_ini_src_path, extracted_livery_path)}", "DETAIL")
                    ini_file_to_copy_src = Path(options_ini_src_path)
                    ini_source_type = "options"
                    ini_file_found = True
                else:
                    # 2. If no options.ini, look for <atc_id>.ini
                    atc_id_ini_filename = f"{atc_id}.ini"
                    atc_id_ini_src_path = self.find_file_in_dir(extracted_livery_path, atc_id_ini_filename.lower())
                    if atc_id_ini_src_path:
                        self.log(f"Found existing '{atc_id_ini_filename}' at: {os.path.relpath(atc_id_ini_src_path, extracted_livery_path)}", "DETAIL")
                        ini_file_to_copy_src = Path(atc_id_ini_src_path)
                        ini_source_type = "atc_id" # Mark that we found the pre-named one
                        ini_file_found = True
                    # else: No relevant ini file found

            if ini_file_found and ini_file_to_copy_src and new_ini_filename:
                 pmdg_localstate_package_path = common_config['pmdg_localstate_package_path'] # Get path for this variant
                 if pmdg_localstate_package_path.is_dir():
                     target_ini_dir = pmdg_localstate_package_path / "work" / "Aircraft"
                     target_ini_path = target_ini_dir / new_ini_filename # Target name is always <atc_id>.ini
                     try:
                         target_ini_dir.mkdir(parents=True, exist_ok=True)
                         shutil.copy2(ini_file_to_copy_src, target_ini_path)
                         if ini_source_type == "options":
                             self.log(f"Renamed options.ini to '{new_ini_filename}' and copied to: {target_ini_dir}", "SUCCESS")
                         else: # Found existing <atc_id>.ini
                             self.log(f"Copied existing '{new_ini_filename}' to: {target_ini_dir}", "SUCCESS")
                         ini_processed_successfully = True
                     except Exception as e:
                         self.log(f"Failed to copy ini file '{ini_file_to_copy_src.name}' to {target_ini_path}: {e}", "ERROR")
                 else:
                      self.log(f"The configured PMDG Package Path for variant {common_config['aircraft_variant']} is not a valid directory: {pmdg_localstate_package_path}", "ERROR")
            elif atc_id: # ATC ID was found, but no ini file
                 self.log("Neither options.ini nor '{atc_id}.ini' found.", "DETAIL")
            else: # ATC ID was not found
                 self.log("Valid atc_id not found in aircraft.cfg, cannot process ini file.", "WARNING")


            # --- Step 6: Modify aircraft.cfg ---
            self.log("Modifying aircraft.cfg for MSFS compatibility...", "INFO")
            try:
                # Pass the livery name detected earlier, NOT the custom one from UI
                self.modify_aircraft_cfg(aircraft_cfg_dest, common_config['aircraft_variant'], livery_name)
            except Exception as e:
                raise RuntimeError(f"Critical step failed: modifying aircraft.cfg: {e}")

            livery_success = True
            error_detail = "Installed successfully."
            if ini_file_found and not ini_processed_successfully: # Add warning if ini found but not processed
                error_detail += f" (Warning: {ini_file_to_copy_src.name} found but failed to process)"


        except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
            error_detail = str(e)
            self.log(f"LIVERY PROCESSING FAILED ({livery_name}): {error_detail}", "ERROR")
            if isinstance(e, (RuntimeError, OSError)):
                import traceback
                self.log(f"Traceback:\n{traceback.format_exc()}", "DETAIL")
            livery_success = False
        except Exception as e: # Catch-all for unexpected errors
            error_detail = f"Unexpected error processing livery {livery_name}: {str(e)}"
            self.log(f"FATAL LIVERY ERROR ({livery_name}): {error_detail}", "ERROR")
            import traceback
            self.log(f"Traceback:\n{traceback.format_exc()}", "DETAIL")
            livery_success = False

        return livery_success, error_detail


    def install_livery_logic(self, archive_paths_to_process):
        """The core installation logic - runs in a separate thread for multiple files."""
        num_files_initial = len(archive_paths_to_process)
        total_processed_count = 0 # Count actual liveries processed (incl. nested)
        success_count = 0
        fail_count = 0
        results = [] # List to store results (filename, success_bool, detail_string)
        manifest_layout_handled = False # Flag to ensure manifest/layout are handled only once

        # --- Get common Configuration (use Path objects) ---
        try:
            community_path = Path(self.community_path_var.get())
            layout_generator_path = Path(self.layout_generator_path_var.get())
            reference_livery_path = Path(self.reference_path_var.get())
            pmdg_paths = {
                "200ER": Path(self.pmdg_77er_path_var.get()),
                "300ER": Path(self.pmdg_77w_path_var.get()),
                "F": Path(self.pmdg_77f_path_var.get())
            }
            aircraft_variant = self.aircraft_variant_var.get()
            pmdg_localstate_package_path = pmdg_paths.get(aircraft_variant)
            if not pmdg_localstate_package_path or not pmdg_localstate_package_path.is_dir():
                raise ValueError(f"Configured PMDG Package Path for variant {aircraft_variant} is invalid or not set.")

            main_package_folder_name = VARIANT_PACKAGE_MAP.get(aircraft_variant)
            main_package_folder = community_path / main_package_folder_name
            main_package_folder_final = str(main_package_folder)
            base_aircraft_folder_name = VARIANT_BASE_AIRCRAFT_MAP.get(aircraft_variant)

            # Create common config dict to pass to helper function
            common_config = {
                'community_path': community_path,
                'layout_generator_path': layout_generator_path,
                'reference_livery_path': reference_livery_path,
                'pmdg_localstate_package_path': pmdg_localstate_package_path,
                'aircraft_variant': aircraft_variant,
                'main_package_folder': main_package_folder,
                'base_aircraft_folder_name': base_aircraft_folder_name,
            }

            # --- Handle Manifest/Layout ONCE before the loop ---
            main_package_folder.mkdir(parents=True, exist_ok=True) # Ensure package folder exists
            manifest_dest = main_package_folder / "manifest.json"
            layout_dest = main_package_folder / "layout.json"

            # Copy manifest if needed
            if not manifest_dest.exists():
                ref_manifest = reference_livery_path / "manifest.json"
                if not ref_manifest.is_file():
                    raise FileNotFoundError(f"Reference manifest.json not found in {reference_livery_path}")
                self.log(f"Copying manifest.json from reference: {reference_livery_path}", "INFO")
                try:
                    shutil.copy2(ref_manifest, manifest_dest)
                    if not manifest_dest.is_file(): # Verify copy succeeded
                        raise RuntimeError("Failed to verify manifest.json copy.")
                    self.log("manifest.json copied successfully from reference.", "DETAIL")
                except Exception as e:
                     raise RuntimeError(f"Failed to copy reference manifest.json: {e}") # Make this fatal before loop

            # Update manifest (always try)
            try:
                with open(manifest_dest, 'r+', encoding='utf-8') as f:
                    try: manifest_data = json.load(f)
                    except json.JSONDecodeError: manifest_data = {}
                    new_manifest_data = {
                        "dependencies": manifest_data.get("dependencies", []), "content_type": "LIVERY",
                        "title": f"Livery Pack: PMDG {aircraft_variant}",
                        "manufacturer": manifest_data.get("manufacturer", ""), "creator": "Community / PMDG Livery Installer Tool",
                        "package_version": manifest_data.get("package_version", "1.0.0"), "minimum_game_version": DEFAULT_MIN_GAME_VERSION,
                        "release_notes": manifest_data.get("release_notes", {})
                    }
                    f.seek(0); json.dump(new_manifest_data, f, indent=4); f.truncate()
                self.log("Checked/Updated manifest.json.", "INFO")
            except Exception as e:
                # Log error but continue if manifest exists, otherwise raise
                if manifest_dest.exists():
                     self.log(f"ERROR updating manifest.json: {e}. Package might not load correctly.", "ERROR") # Changed level to ERROR
                else:
                     raise RuntimeError(f"ERROR: manifest.json missing and update failed: {e}") # Make this fatal


            # Copy layout if needed
            if not layout_dest.exists():
                ref_layout = reference_livery_path / "layout.json"
                if ref_layout.is_file():
                    self.log(f"Copying layout.json template from reference: {reference_livery_path}", "INFO")
                    try:
                        shutil.copy2(ref_layout, layout_dest)
                        if not layout_dest.is_file():
                             self.log("layout.json copy attempted but file not found at destination!", "WARNING")
                    except Exception as e:
                        self.log(f"Failed to copy reference layout.json: {e}. Generator may create a new one.", "WARNING")
                else:
                    self.log(f"Reference layout.json not found in {reference_livery_path}. MSFSLayoutGenerator will need to create a new one.", "WARNING")
            manifest_layout_handled = True

        except Exception as config_e:
            self.log(f"CRITICAL ERROR: Could not get initial configuration or handle manifest/layout: {config_e}", "ERROR")
            self.master.after(0, lambda: self.status_var.set("Installation failed! (Configuration/Manifest Error)"))
            self.master.after(0, lambda: self.install_button.config(state=tk.NORMAL))
            messagebox.showerror("Critical Error", f"Could not read necessary configuration or handle manifest/layout:\n{config_e}")
            return

        # --- Process each selected archive path ---
        for index, archive_path_str in enumerate(archive_paths_to_process):
            livery_archive_path = Path(archive_path_str)
            archive_name = livery_archive_path.name
            self.log(f"--- Processing selected file {index + 1}/{num_files_initial}: {archive_name} ---", "STEP")
            self.master.after(0, lambda idx=index: self.status_var.set(f"Processing {idx + 1}/{num_files_initial}: {archive_name}..."))

            initial_temp_dir = None
            try:
                # Create a unique top-level temp dir for this initial archive
                initial_temp_dir_name = f"__temp_initial_{archive_name}_{datetime.now().strftime('%f')}"
                initial_temp_dir = main_package_folder / initial_temp_dir_name
                initial_temp_dir.mkdir(parents=True, exist_ok=True)

                # Step 1: Extract the initially selected archive
                self._extract_archive(livery_archive_path, initial_temp_dir)

                # Step 1.5: Check if this archive contains nested zips
                if self._is_nested_archive(initial_temp_dir):
                    # Determine the effective directory (might be a single subfolder)
                    items = list(initial_temp_dir.iterdir())
                    nested_check_dir = initial_temp_dir
                    if len(items) == 1 and items[0].is_dir() and not items[0].name.startswith('.'):
                        nested_check_dir = items[0]

                    nested_zips = list(nested_check_dir.glob('*.zip'))
                    self.log(f"Found {len(nested_zips)} nested liveries inside '{archive_name}'. Processing each...", "INFO")
                    for nested_zip_index, nested_zip_path in enumerate(nested_zips):
                        nested_archive_name = nested_zip_path.name
                        self.log(f"--- Processing nested {nested_zip_index + 1}/{len(nested_zips)}: {nested_archive_name} (from {archive_name}) ---", "STEP")
                        nested_temp_dir = None
                        try:
                            # Create a sub-temp dir for the nested zip
                            nested_temp_dir_name = f"__temp_nested_{nested_archive_name}_{datetime.now().strftime('%f')}"
                            nested_temp_dir = initial_temp_dir / nested_temp_dir_name # Create nested temp inside initial temp
                            nested_temp_dir.mkdir(exist_ok=True)

                            # Extract the nested zip
                            self._extract_archive(nested_zip_path, nested_temp_dir)

                            # Process this single extracted nested livery
                            livery_success, detail = self._process_single_livery(nested_temp_dir, nested_zip_path, common_config)
                            results.append({"file": f"{archive_name} -> {nested_archive_name}", "success": livery_success, "detail": detail})
                            total_processed_count += 1
                            if livery_success: success_count += 1
                            else: fail_count += 1

                        except Exception as nested_e:
                            error_detail = f"Error processing nested zip '{nested_archive_name}': {nested_e}"
                            self.log(error_detail, "ERROR")
                            results.append({"file": f"{archive_name} -> {nested_archive_name}", "success": False, "detail": error_detail})
                            fail_count += 1
                            total_processed_count += 1
                        finally:
                            # Clean up nested temp dir
                            if nested_temp_dir and nested_temp_dir.exists():
                                try: shutil.rmtree(nested_temp_dir)
                                except Exception as e: self.log(f"Could not remove nested temporary folder {nested_temp_dir}: {e}", "WARNING")
                else:
                    # Not nested, process the contents of initial_temp_dir directly
                    # Determine the effective directory (might be a single subfolder)
                    items = list(initial_temp_dir.iterdir())
                    single_livery_dir = initial_temp_dir
                    if len(items) == 1 and items[0].is_dir() and not items[0].name.startswith('.'):
                        single_livery_dir = items[0]
                        self.log(f"Processing single livery found inside subfolder '{single_livery_dir.name}' of '{archive_name}'.", "INFO")
                    else:
                         self.log(f"Processing '{archive_name}' as a single livery.", "INFO")

                    livery_success, detail = self._process_single_livery(single_livery_dir, livery_archive_path, common_config)
                    results.append({"file": archive_name, "success": livery_success, "detail": detail})
                    total_processed_count += 1
                    if livery_success: success_count += 1
                    else: fail_count += 1

            except Exception as outer_e:
                # Error processing the initially selected archive (e.g., extraction failed)
                error_detail = f"Error processing initial archive '{archive_name}': {outer_e}"
                self.log(error_detail, "ERROR")
                results.append({"file": archive_name, "success": False, "detail": error_detail})
                fail_count += 1
                # Don't increment total_processed_count here as no livery was actually processed
            finally:
                # Clean up the top-level temp dir for this initial archive
                if initial_temp_dir and initial_temp_dir.exists():
                    try: shutil.rmtree(initial_temp_dir)
                    except Exception as e: self.log(f"Could not remove initial temporary folder {initial_temp_dir}: {e}", "WARNING")

            # --- Update overall progress based on initial files processed ---
            progress_value = ((index + 1) / num_files_initial) * 85 # Max 85% before layout gen
            self.master.after(0, lambda p=progress_value: self.progress_var.set(p))


        # --- End of loop ---

        # --- Step 7: Automatic Layout Generation (Run ONCE after all files are processed) ---
        layout_gen_success = False
        layout_gen_error_detail = ""
        if success_count > 0: # Only run if at least one livery was potentially installed correctly
            self.log("--- Starting layout.json generation (once for all liveries) ---", "STEP") # English
            self.master.after(0, lambda: self.status_var.set("Generating layout.json...")) # English
            layout_dest = main_package_folder / "layout.json"
            if not layout_generator_path.is_file():
                 layout_gen_error_detail = f"MSFSLayoutGenerator.exe not found at specified path: {layout_generator_path}" # English
                 self.log(layout_gen_error_detail, "ERROR")
            else:
                command = [str(layout_generator_path), str(layout_dest.name)]
                self.log(f"Executing command: {' '.join(command)} in folder {main_package_folder}", "CMD") # English
                try:
                    creationflags = 0
                    if sys.platform == "win32": creationflags = subprocess.CREATE_NO_WINDOW
                    result = subprocess.run(command, cwd=main_package_folder, check=True,
                                            capture_output=True, text=True, encoding='utf-8',
                                            errors='ignore', timeout=180, # Increased timeout slightly
                                            creationflags=creationflags)
                    self.log("MSFSLayoutGenerator executed successfully.", "SUCCESS") # English
                    layout_gen_success = True
                    self.master.after(0, lambda: self.progress_var.set(100)) # Final progress
                except subprocess.CalledProcessError as e:
                    self.log(f"MSFSLayoutGenerator failed with exit code {e.returncode}.", "ERROR") # English
                    if e.stdout: self.log(f"Generator Output (stdout):\n{e.stdout}", "DETAIL") # English
                    if e.stderr: self.log(f"Generator Error Output (stderr):\n{e.stderr}", "ERROR") # English
                    layout_gen_error_detail = f"MSFSLayoutGenerator failed (Code: {e.returncode}). Check log. You may need to run it manually." # English
                except FileNotFoundError:
                     layout_gen_error_detail = f"Failed to execute MSFSLayoutGenerator. Path might be incorrect or file missing: {layout_generator_path}" # English
                     self.log(layout_gen_error_detail, "ERROR")
                except subprocess.TimeoutExpired:
                     layout_gen_error_detail = "MSFSLayoutGenerator timed out after 180 seconds. Check if it's stuck or try running it manually." # English
                     self.log(layout_gen_error_detail, "ERROR")
                except Exception as e:
                     layout_gen_error_detail = f"Unexpected error running MSFSLayoutGenerator: {e}. Check log." # English
                     self.log(f"Unexpected error running MSFSLayoutGenerator: {e}", "ERROR") # English
                     import traceback
                     self.log(f"Traceback:\n{traceback.format_exc()}", "DETAIL")
        else:
            self.log("Skipping layout.json generation because all livery installations failed.", "WARNING") # English


        # --- Final Notification (called on main thread) ---
        final_overall_success = (fail_count == 0 and layout_gen_success)
        final_status_message = "Completed" if final_overall_success else "Completed with errors" if success_count > 0 else "Failed" # English
        self.master.after(0, lambda msg=final_status_message: self.status_var.set(msg))
        self.master.after(0, lambda: self.install_button.config(state=tk.NORMAL)) # Re-enable button
        # Pass the results list (now contains nested results too) and layout status
        self.master.after(100, lambda: self.show_multi_final_message(results, layout_gen_success, layout_gen_error_detail, main_package_folder_final))


    # ========================================================================
    # <<< !!! AIRCRAFT.CFG MODIFICATION (v1.8.4 - Title Fix) !!! >>>
    # ========================================================================
    def modify_aircraft_cfg(self, cfg_path: Path, aircraft_variant: str, livery_title: str):
        """
        Reads, modifies aircraft.cfg, and writes back.
        - Modifies 'base_container' ONLY under the [VARIATION] section,
          preserving the engine suffix (GE, RR, PW) for 777-200ER if found,
          AND ENSURING the value is ALWAYS enclosed in double quotes.
        - DOES NOT modify 'title' under [fltsim.X] sections anymore.
        - DOES NOT add or modify 'base_container' under [fltsim.X].
        """
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Cannot modify aircraft.cfg, file not found: {cfg_path}") # English

        correct_base_folder_name = VARIANT_BASE_AIRCRAFT_MAP.get(aircraft_variant)
        if not correct_base_folder_name:
            raise ValueError(f"Invalid variant '{aircraft_variant}' for aircraft.cfg.") # English

        # --- Read the existing file content ---
        try:
            lines = cfg_path.read_text(encoding='utf-8', errors='ignore').splitlines(keepends=True)
        except Exception as e:
            raise RuntimeError(f"Error reading aircraft.cfg file '{cfg_path}': {e}") # English

        # --- Determine the TARGET base_container value for [VARIATION] (ALWAYS QUOTED) ---
        target_variation_base_container_value = f'"..\\{correct_base_folder_name}"' # Default target includes quotes
        engine_suffix = ""

        if aircraft_variant == "200ER":
            # ... (Engine suffix detection logic remains the same) ...
            self.log("Processing 777-200ER: Checking for engine suffix in original [VARIATION]...", "DETAIL") # English
            in_variation_section_read = False
            original_variation_base_container_line = None
            for line in lines:
                stripped_line = line.strip()
                if stripped_line.lower() == '[variation]': in_variation_section_read = True; continue
                if in_variation_section_read:
                    if stripped_line.startswith('['): break
                    if re.match(r'^\s*base_container\s*=', stripped_line, re.IGNORECASE): original_variation_base_container_line = line; break
            if original_variation_base_container_line:
                bc_match_read = re.match(r'^\s*base_container\s*=\s*"?(.+?)"?\s*$', original_variation_base_container_line.strip(), re.IGNORECASE)
                if bc_match_read:
                    existing_value_unquoted = bc_match_read.group(1).strip().replace('/', '\\')
                    base_name_pattern = re.escape(correct_base_folder_name).replace('\\\\', '\\')
                    engine_match = re.search(rf'{base_name_pattern}\s+(GE|RR|PW)\b', existing_value_unquoted, re.IGNORECASE)
                    if engine_match:
                        engine_suffix = " " + engine_match.group(1).upper()
                        self.log(f"Detected and preserving engine suffix '{engine_suffix.strip()}' from [VARIATION] base_container: '{existing_value_unquoted}'", "INFO") # English
                        target_variation_base_container_value = f'"..\\{correct_base_folder_name}{engine_suffix}"'
                    else:
                        self.log(f"[VARIATION] base_container '{existing_value_unquoted}' did not contain recognized engine suffix. Using default.", "DETAIL") # English
                        target_variation_base_container_value = f'"..\\{correct_base_folder_name}"'
                else:
                    self.log("Could not parse existing [VARIATION] base_container line value.", "WARNING") # English
                    target_variation_base_container_value = f'"..\\{correct_base_folder_name}"'
            else:
                 self.log("No base_container line found in [VARIATION] section to check for engine suffix. Using default target.", "DETAIL") # English
                 target_variation_base_container_value = f'"..\\{correct_base_folder_name}"'
        else:
            target_variation_base_container_value = f'"..\\{correct_base_folder_name}"'


        self.log(f"Target [VARIATION] base_container value set to: {target_variation_base_container_value}", "DETAIL") # English
        target_variation_bc_line_content = f'base_container = {target_variation_base_container_value}'

        # --- Process the file line by line for writing ---
        variation_regex = re.compile(r'^\s*\[VARIATION\]', re.IGNORECASE)
        fltsim_regex = re.compile(r'^\s*\[FLTSIM\.(\d+)\]', re.IGNORECASE)
        base_container_regex = re.compile(r'^\s*base_container\s*=\s*(.*)', re.IGNORECASE)
        # title_regex = re.compile(r'^\s*title\s*=\s*(.*)', re.IGNORECASE) # No longer needed

        needs_write = False
        output_lines = []
        in_variation_section = False
        in_fltsim_section = False
        current_fltsim_index = -1
        found_variation_bc = False
        # found_fltsim_title = False # No longer needed

        for i, line in enumerate(lines):
            stripped_line = line.strip()
            original_indent = line[:len(line) - len(line.lstrip())]

            # --- Section Detection ---
            if variation_regex.match(stripped_line):
                in_variation_section = True; in_fltsim_section = False; found_variation_bc = False
                output_lines.append(line); continue
            elif fltsim_regex.match(stripped_line):
                if in_variation_section and not found_variation_bc:
                    self.log("Adding missing base_container line to [VARIATION] section.", "INFO") # English
                    output_lines.append(f"{original_indent}{target_variation_bc_line_content}\n"); needs_write = True; found_variation_bc = True
                in_variation_section = False; in_fltsim_section = True
                current_fltsim_index = int(fltsim_regex.match(stripped_line).group(1)); # found_fltsim_title = False # No longer needed
                output_lines.append(line); continue
            elif stripped_line.startswith('['):
                if in_variation_section and not found_variation_bc:
                     self.log("Adding missing base_container line to [VARIATION] section.", "INFO") # English
                     prev_indent = "    ";
                     if output_lines: prev_indent = output_lines[-1][:len(output_lines[-1]) - len(output_lines[-1].lstrip())]
                     output_lines.append(f"{prev_indent}{target_variation_bc_line_content}\n"); needs_write = True; found_variation_bc = True
                in_variation_section = False; in_fltsim_section = False
                output_lines.append(line); continue


            # --- Line Modification ---
            line_modified_this_pass = False

            # Modify base_container ONLY if in [VARIATION] section
            if in_variation_section:
                bc_match = base_container_regex.match(stripped_line)
                if bc_match:
                    found_variation_bc = True
                    line_modified_this_pass = True
                    existing_value_part = bc_match.group(1).strip()
                    if existing_value_part == target_variation_base_container_value:
                        output_lines.append(line)
                    else:
                        self.log(f"Ensuring correct quotes in [VARIATION] base_container. Old value: '{existing_value_part}', Target line: '{target_variation_bc_line_content}'", "INFO") # English
                        new_line = f"{original_indent}{target_variation_bc_line_content}\n"
                        output_lines.append(new_line)
                        needs_write = True

            # --- REMOVED TITLE MODIFICATION LOGIC ---

            if not line_modified_this_pass:
                output_lines.append(line)

        # --- After processing all lines ---
        if in_variation_section and not found_variation_bc:
             self.log("Adding missing base_container line to [VARIATION] section at end of file.", "INFO") # English
             prev_indent = "    "
             if output_lines: prev_indent = output_lines[-1][:len(output_lines[-1]) - len(output_lines[-1].lstrip())]
             output_lines.append(f"{prev_indent}{target_variation_bc_line_content}\n")
             needs_write = True

        # --- Write back if changes were made ---
        if needs_write:
            try:
                cfg_path.write_text("".join(output_lines), encoding='utf-8', errors='ignore')
                self.log("Successfully updated aircraft.cfg with required modifications (incl. VARIATION quotes).", "SUCCESS") # English
            except Exception as e:
                raise RuntimeError(f"Error writing updated aircraft.cfg file '{cfg_path}': {e}") # English
        else:
            self.log("No modifications needed for aircraft.cfg.", "DETAIL") # English

    # ========================================================================
    # <<< END OF AIRCRAFT.CFG MODIFICATION >>>
    # ========================================================================


    def show_multi_final_message(self, results, layout_success, layout_detail, install_path):
        """Shows the final success/failure message box for multiple installations."""
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count
        total_processed = len(results)
        title = "Installation Result" # English
        summary_lines = []

        if fail_count == 0:
            if layout_success:
                summary_lines.append(f"{success_count}/{total_processed} liveries installed and layout generated successfully!") # English
                summary_lines.append("\nThe liveries should now be available in MSFS.") # English
                summary_lines.append("(Restart MSFS if it was running).") # English
                log_level = "SUCCESS"
                msg_type = messagebox.showinfo
            else:
                summary_lines.append(f"{success_count}/{total_processed} liveries copied, but layout.json generation failed!") # English
                summary_lines.append(f"\nLayout Error: {layout_detail}") # English
                summary_lines.append("\nCheck the log and Help tab for possible solutions (e.g., run manually).") # English
                log_level = "WARNING"
                msg_type = messagebox.showwarning
        else:
            summary_lines.append(f"Installation completed with {fail_count} error(s).") # English
            summary_lines.append(f" - Successful: {success_count}/{total_processed}") # English
            summary_lines.append(f" - Failed: {fail_count}/{total_processed}") # English
            if not layout_success and success_count > 0:
                 summary_lines.append(f"\nAdditionally, layout.json generation failed!") # English
                 summary_lines.append(f"Layout Error: {layout_detail}") # English
            elif not layout_success and success_count == 0:
                 summary_lines.append(f"\nLayout.json generation was skipped or failed.") # English


            summary_lines.append("\nError details (check log for more info):") # English
            # Limit displayed errors in message box for brevity
            errors_to_show = 0
            max_errors_in_box = 5
            for result in results:
                if not result["success"] and errors_to_show < max_errors_in_box:
                    # Truncate long error details
                    detail = result['detail']
                    if len(detail) > 150:
                        detail = detail[:147] + "..."
                    summary_lines.append(f" - {result['file']}: {detail}")
                    errors_to_show += 1
            if fail_count > max_errors_in_box:
                summary_lines.append(f"   (... and {fail_count - max_errors_in_box} more errors. Check log.)") # English

            log_level = "ERROR"
            msg_type = messagebox.showerror

        final_message = "\n".join(summary_lines)
        self.log(f"Multi-Install Summary: {success_count}/{total_processed} successful, {fail_count} failed. Layout OK: {layout_success}", log_level) # English
        msg_type(title, final_message)


    def on_close(self):
        """Handle window close event: save config and destroy."""
        self.log("Saving configuration on exit...", "DETAIL") # English
        self.save_config() # Attempt to save config
        self.master.destroy()

# --- Main Execution ---
def main():
    # Improve DPI awareness on Windows if possible
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass # Ignore errors if not applicable

    root = tk.Tk()
    app = PMDGLiveryInstaller(root)
    root.mainloop()

if __name__ == "__main__":
    main()

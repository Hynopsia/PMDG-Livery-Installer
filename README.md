# PMDG 777 & 737 NG Livery Installer (Unofficial)

**Version:** v2.1.1

An unofficial, standalone tool to help install third-party liveries in `.zip` or `.ptp` format for the PMDG 777 family (777-200ER, 777-300ER, 777F) AND the PMDG 737 NG family (737-600, -700, -800, -900 series, including variants like BBJ, BCF, BDSF, ER) in Microsoft Flight Simulator (MSFS 2020).

## Problem Solved

This tool provides an alternative installation method for users who have encountered issues with liveries not appearing correctly, aircraft configuration errors, or state/option `.ini` files not being properly handled when using other methods or manual installation. It automates several tedious and error-prone steps.

## Key Features

- **Broad Aircraft Support:** Installs liveries for:
  - **PMDG 777:** 777-200ER, 777-300ER, 777F.
  - **PMDG 737 NG:** 737-600, 737-700 (incl. BBJ, BDSF), 737-800 (incl. BBJ2, BCF, BDSF), 737-900 (incl. ER).
- **Flexible Input:**
  - Installs liveries from `.zip` or `.ptp` archives.
  - Supports selecting multiple archive files at once (all files **must** be for the same aircraft variant selected in the UI).
- **Advanced PTP Handling:**
  - Utilizes the included `ptp_converter.exe` for robust extraction.
  - Supports **multi-livery PTP archives** (those containing multiple liveries defined in a `Settings.dat` file), extracting and installing each sub-livery.
  - Standardizes PTP output (e.g., `Config.cfg` to `aircraft.cfg`, `Aircraft.ini` to `options.ini`).
- **Archive Support:** Handles nested `.zip` files (e.g., "pack" archives containing individual livery zips or PTPs).
- **Correct File Placement:** Places livery files (`texture.*`, `model` or `model.XXX`, `aircraft.cfg`, etc.) into the appropriate `pmdg-aircraft-7XX-liveries` folder in your Community folder.
- **Intelligent `aircraft.cfg` Modification:**
  - Corrects the `base_container` path in the `[VARIATION]` section for the selected aircraft.
  - Preserves engine type suffix (GE/RR/PW) for the 777-200ER `base_container`.
  - Ensures proper formatting of `[FLTSIM.0]`, `[VARIATION]`, and `[VERSION]` sections.
  - Corrects common `ttitle=` typo to `title=`.
  - Uses the livery's detected or user-provided name for the `title=` field.
- **PMDG State/Options `.ini` File Management:**
  - Looks for `options.ini` (or `Aircraft.ini` from PTPs) or `<atc_id>.ini` within the livery's files.
  - Renames `options.ini` to `<atc_id>.ini` (using the `atc_id` from the `aircraft.cfg`).
  - Copies the correctly named `.ini` file to the aircraft's specific `work\Aircraft` folder within your MSFS `LocalState\packages` directory (requires correct setup of PMDG Base Package Paths).
- **Automatic Package Management:**
  - Generates `layout.json` for the entire livery package.
  - Updates `manifest.json` with correct dependencies, `total_package_size`, and `LastUpdate` timestamp.
- **User-Friendly Interface:**
  - Clear setup and installation tabs.
  - Detailed installation log.
  - Help tab with guidance.

## Disclaimer / Important Notes

- **USE AT YOUR OWN RISK:** While tested, bugs may exist. Backup your Community folder and `LocalState\packages` PMDG aircraft folders if you are concerned.
- **UNOFFICIAL:** This tool is not affiliated with or endorsed by PMDG or Microsoft.
- **MSFS 2020 ONLY:** Developed and tested only for Microsoft Flight Simulator (2020).
- **MSFS 2024 UNTESTED:** This tool has **NOT** been tested with MSFS 2024. It _might_ work if folder structures remain similar, but there is **NO GUARANTEE**.
- **SUPPORTED AIRCRAFT ONLY:** Designed specifically for the PMDG 777 and PMDG 737 NG families listed above. It will **NOT** work for other aircraft.
- **SUPPORTED ARCHIVES:** Handles `.zip` and `.ptp` archives. For `.ptp` processing, `ptp_converter.exe` (included) is required. RAR archives are NOT supported.
- **ANTIVIRUS FALSE POSITIVES:** Executables created with tools like PyInstaller can sometimes be flagged by antivirus software. The source code is provided for transparency. Consider creating your own executable from source if concerned.

## Download

1.  Go to the [**Releases**](https://github.com/semartinezmo/PMDG-Livery-Installer/releases) page of this repository.
2.  Under the latest release (e.g., `v2.1.0`), download the main `.zip` file (e.g., `PMDGLiveryInstaller_v2.1.0.zip`).
3.  This package includes `PMDGLiveryInstaller.exe`, `ptp_converter.exe`, and `icon.ico`.

## Usage

1.  **Unzip:** Extract the entire contents of the downloaded `.zip` file to a folder on your computer. **All extracted files (`PMDGLiveryInstaller.exe`, `ptp_converter.exe`, `icon.ico`) must be kept in the same folder for the application to work correctly, especially PTP processing.**
2.  **Run:** Double-click `PMDGLiveryInstaller.exe`.
3.  **Setup Tab:**
    - **MSFS Community Folder:** Browse to and select your main MSFS Community folder.
    - **PMDG Aircraft Base Package Paths (LocalState/packages - for .ini files):** For each PMDG aircraft base package you own (e.g., 777-200ER, 737-600, 737-700 Base for all 700 variants, etc.), browse to its specific package folder within your MSFS `LocalState\packages` directory.
      - Example paths to select: `...\LocalState\packages\pmdg-aircraft-77er`, `...\LocalState\packages\pmdg-aircraft-737` (for 737-700/BBJ/BDSF), `...\LocalState\packages\pmdg-aircraft-738` (for 737-800/BBJ2/BCF/BDSF), etc.
      - This is crucial for the `.ini` file handling.
    - **Reference PMDG Livery Folder:** Browse to and select the main folder of _any_ correctly installed PMDG 777 or 737 livery inside its Community package (e.g., `Community\pmdg-aircraft-77w-liveries\SimObjects\Airplanes\PMDG 777-300ER Example Livery` or `Community\pmdg-aircraft-737-liveries\SimObjects\Airplanes\PMDG 737-700 Example Livery`). This is used for template files if a new livery package needs to be created.
    - Click **Save Settings**.
4.  **Install Livery(s) Tab:**
    - Click **Browse...** next to "Livery File(s)" and select one or more `.zip` or `.ptp` livery archive files.
    - **Select Aircraft Series:** Choose "Boeing 777" or "Boeing 737 NG".
    - **Select Variant/Sub-Model:** Based on the series, choose the specific aircraft model (e.g., "777-300ER", "737-800BCF"). **This is mandatory.**
    - If installing multiple files, they _must_ all be for the selected variant.
    - (Optional) If you selected only _one_ file, you can enter a custom name for it in the "Livery Name (in sim)" box. Otherwise, the name will be auto-detected.
    - Click **Install Livery(s) & Generate Layout**.
5.  **Check Log:** Monitor the "Installation Log" window for progress and any errors.
6.  **Restart MSFS:** If MSFS was running during the installation, restart it to see the new liveries.

## Requirements

- Windows Operating System.
- Microsoft Flight Simulator (MSFS 2020).
- PMDG 777 and/or PMDG 737 NG aircraft package(s) installed.
- `ptp_converter.exe` (included) must be in the same folder as `PMDGLiveryInstaller.exe` for PTP file processing.
- **Recommended for Windows 10/11:** Enable "Win32 long paths" system-wide for best compatibility with MSFS's long file paths. (This application is also packaged to be long-path aware).

## Feedback / Issues

Please report any bugs or suggest features using the [**Issues**](https://github.com/semartinezmo/PMDG-Livery-Installer/issues) tab on GitHub. Provide details from the Installation Log if reporting errors.

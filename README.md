# PMDG 777 Livery Installer (Unofficial)

**Version:** v1.10.2

An unofficial, standalone tool to help install third-party liveries in `.zip` or `.ptp` format for the PMDG 777 family (777-200ER, 777-300ER, 777F) in Microsoft Flight Simulator (2020). This tool now features an English user interface.

## Problem Solved

This tool aims to provide an alternative installation method for users who have encountered issues with liveries not appearing correctly or state/option `.ini` files not being properly handled when using other methods.

## Features

- Installs liveries from `.zip` or `.ptp` archives (supports selecting multiple files at once, **if they are all for the same aircraft variant**).
- For `.ptp` files, utilizes the included `ptp_converter.exe` for extraction and processing.
- Handles nested `.zip` files (e.g., "pack" archives containing individual livery zips or ptps).
- Correctly places livery files (`texture.*`, `model` or `model.XXX`, `aircraft.cfg`, etc.) into the appropriate `pmdg-aircraft-77X-liveries` folder in your Community folder.
- Modifies the `aircraft.cfg` file:
  - Corrects the `base_container` path in the `[VARIATION]` section.
  - Preserves the engine type suffix (GE/RR/PW) for the 777-200ER in the `base_container`.
  - Ensures the `base_container` value is enclosed in double quotes.
  - Leaves the `title` field in `[FLTSIM.X]` sections untouched (uses PTP/ZIP provided title).
  - For PTPs, correctly names the `model.XXX` folder based on the `model=` line in the original PTP configuration and preserves this line.
- Handles PMDG state/options files:
  - Looks for `options.ini` (or `Aircraft.ini` from PTPs, which is renamed to `options.ini`) or `<atc_id>.ini` within the livery's files.
  - Renames `options.ini` to `<atc_id>.ini` (using the `atc_id` from the `aircraft.cfg`).
  - Copies the correctly named `.ini` file to the aircraft's specific `work\Aircraft` folder within your MSFS `LocalState\packages` directory (requires configuration).
- Automatically generates `layout.json` and updates `manifest.json` (including `total_package_size` and dependencies) internally for the livery package. No external tools required for this step.
- User interface translated to English.
- Fixes bug where livery name field did not clear after PTP installation.

## Disclaimer / Important Notes

- **USE AT YOUR OWN RISK:** While tested, bugs may exist. Backup your Community folder and LocalState PMDG folders if you are concerned.
- **UNOFFICIAL:** This tool is not affiliated with or endorsed by PMDG or Microsoft.
- **MSFS 2020 ONLY:** Developed and tested only for Microsoft Flight Simulator (2020).
- **MSFS 2024 UNTESTED:** This tool has **NOT** been tested with MSFS 2024. It _might_ work if folder structures remain similar, but there is **NO GUARANTEE**.
- **PMDG 777 ONLY:** Designed specifically for the PMDG 777-200ER, 777-300ER, and 777F. It will **NOT** work for other aircraft.
- **SUPPORTED ARCHIVES:** Handles `.zip` and `.ptp` archives. For `.ptp` processing, `ptp_converter.exe` (included with this tool) is required.
- **ANTIVIRUS FALSE POSITIVES:** Executables created with tools like PyInstaller can sometimes be flagged by antivirus software. The source code is provided for transparency. Consider creating your own executable from source if concerned.

## Download

1.  Go to the [**Releases**](https://github.com/semartinezmo/PMDG-Livery-Installer/releases) page of this repository.
2.  Under the latest release (e.g., `v1.10.2`), download the main `.zip` file containing the application (e.g., `PMDG777LiveryInstaller_v1.10.2.zip`).
3.  This package includes `PMDG777LiveryInstaller.exe`, `ptp_converter.exe`, and `icon.ico`.

## Usage

1.  **Unzip:** Extract the entire contents of the downloaded `.zip` file to a folder on your computer. **All extracted files (`PMDG777LiveryInstaller.exe`, `ptp_converter.exe`, `icon.ico`) must be kept in the same folder for the application to work correctly, especially PTP processing.**
2.  **Run:** Double-click the `PMDG777LiveryInstaller.exe` file.
3.  **Setup Tab:**
    - **MSFS Community Folder:** Browse to and select your main MSFS Community folder.
    - **PMDG Package Paths (LocalState):** For each PMDG 777 variant you own, browse to its specific package folder within `...AppData\Local\Packages\Microsoft.FlightSimulator_...\LocalState\packages\`. Select the folder named `pmdg-aircraft-77er`, `pmdg-aircraft-77w`, or `pmdg-aircraft-77f`. This is needed for the `options.ini` handling.
    - **Reference 777 Livery Folder:** Browse to and select the main folder of _any_ correctly installed PMDG 777 livery inside your Community folder (e.g., `Community\pmdg-aircraft-77w-liveries\SimObjects\Airplanes\PMDG 777-300ER Example Livery`). This is used for template files if a new livery package needs to be created.
    - Click **Save Settings**.
4.  **Install Livery(s) Tab:**
    - Click **Browse...** next to "Livery File(s)" and select one or more `.zip` or `.ptp` files.
    - **Select the correct Aircraft Variant** using the radio buttons. **This is mandatory.** If installing multiple files, they _must_ all be for this selected variant.
    - (Optional) If you selected only _one_ file, you can enter a custom name for it in the "Livery Name (in sim)" box. Otherwise, the name will be auto-detected or taken from the livery's configuration.
    - Click **Install Livery(s) & Generate Layout**.
5.  **Check Log:** Monitor the "Installation Log" window for progress and any errors.
6.  **Restart MSFS:** If MSFS was running during the installation, restart it to see the new liveries.

## Requirements

- Windows Operating System.
- Microsoft Flight Simulator (2020).
- PMDG 777 Aircraft Package(s) installed.
- `ptp_converter.exe` (included with this tool) must be in the same folder as `PMDG777LiveryInstaller.exe` for PTP file processing.
- **Recommended for Windows 10/11:** Enable "Win32 long paths" system-wide for best compatibility with MSFS's long file paths. (This application is also packaged to be long-path aware).

## Feedback / Issues

Please report any bugs or suggest features using the [**Issues**](https://github.com/semartinezmo/PMDG-Livery-Installer/issues) tab on GitHub. Provide details from the Installation Log if reporting errors.

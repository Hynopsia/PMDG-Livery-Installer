# PMDG 777 Livery Installer (Unofficial)

**Version:** v1.8.5 (Alpha)

An unofficial, standalone tool to help install third-party liveries in `.zip` format for the PMDG 777 family (777-200ER, 777-300ER, 777F) in Microsoft Flight Simulator (2020).

## Problem Solved

This tool aims to provide an alternative installation method for users who have encountered issues with liveries not appearing correctly or state/option `.ini` files not being properly handled when using other methods, including the PMDG Operations Center for _third-party_ liveries.

## Features

- Installs liveries from `.zip` archives (supports selecting multiple `.zip` files at once, **if they are all for the same aircraft variant**).
- Handles nested `.zip` files (e.g., "pack" archives containing individual livery zips).
- Correctly places livery files (`texture.*`, `model`, `aircraft.cfg`, etc.) into the appropriate `pmdg-aircraft-77X-liveries` folder in your Community folder.
- Modifies the `aircraft.cfg` file:
  - Corrects the `base_container` path in the `[VARIATION]` section.
  - Preserves the engine type suffix (GE/RR/PW) for the 777-200ER in the `base_container`.
  - Ensures the `base_container` value is enclosed in double quotes.
  - Leaves the `title` field in `[FLTSIM.X]` sections untouched.
- Handles PMDG state/options files:
  - Looks for `options.ini` _or_ `<atc_id>.ini` within the livery's files.
  - Renames `options.ini` to `<atc_id>.ini` (using the `atc_id` from the `aircraft.cfg`).
  - Copies the correctly named `.ini` file to the aircraft's specific `work\Aircraft` folder within your MSFS `LocalState\packages` directory (requires configuration).
- Automatically runs the `MSFSLayoutGenerator.exe` tool (must be configured) to update the `layout.json` for the livery package.
- Simple graphical user interface (GUI).

## Disclaimer / Important Notes

- **ALPHA SOFTWARE:** This is an early version. Use at your own risk. Bugs may exist. Backup your Community folder and LocalState PMDG folders if you are concerned.
- **UNOFFICIAL:** This tool is not affiliated with or endorsed by PMDG or Microsoft.
- **MSFS 2020 ONLY:** Developed and tested only for Microsoft Flight Simulator (2020).
- **MSFS 2024 UNTESTED:** This tool has **NOT** been tested with MSFS 2024. It _might_ work if folder structures remain similar, but there is **NO GUARANTEE**.
- **PMDG 777 ONLY:** Designed specifically for the PMDG 777-200ER, 777-300ER, and 777F. It will **NOT** work for other aircraft.
- **ZIP SUPPORT ONLY:** Only handles `.zip` archives. It cannot process PMDG's official `.ptp` files (use the PMDG Operations Center for those).
- **ANTIVIRUS FALSE POSITIVES:** Executables created with tools like PyInstaller or Nuitka can sometimes be flagged by antivirus software (false positive). This is often due to how the application is bundled. The source code is provided here for transparency. You can check the VirusTotal scan results for the release executable [Optional: Add Link to VirusTotal result here].

## Download

1.  Go to the [**Releases**](https://github.com/semartinezmo/PMDG-Livery-Installer/releases) page of this repository.
2.  Under the latest release (e.g., `v1.8.5`), look for the `.zip` file in the "Assets" section (e.g., `PMDG777LiveryInstaller_v1.8.5.zip`).
3.  Download the `.zip` file.

## Usage

1.  **Unzip:** Extract the entire contents of the downloaded `.zip` file to a folder on your computer.
2.  **Run:** Double-click the `PMDG777LiveryInstaller.exe` file inside the extracted folder.
3.  **Configuration Tab:**
    - **MSFS Community Folder:** Browse to and select your main MSFS Community folder.
    - **PMDG Package Paths (LocalState):** For each PMDG 777 variant you own, browse to its specific package folder within `...AppData\Local\Packages\Microsoft.FlightSimulator_...\LocalState\packages\`. Select the folder named `pmdg-aircraft-77er`, `pmdg-aircraft-77w`, or `pmdg-aircraft-77f`. This is needed for the `options.ini` handling.
    - **MSFSLayoutGenerator.exe:** Browse to and select the `MSFSLayoutGenerator.exe` tool (download it if you don't have it).
    - **Reference 777 Livery Folder:** Browse to and select the main folder of _any_ correctly installed PMDG 777 livery inside your Community folder (e.g., `Community\pmdg-aircraft-77w-liveries\SimObjects\Airplanes\PMDG 777-300ER Example Livery`). This is used for template files.
    - Click **Save Configuration**.
4.  **Install Livery(s) Tab:**
    - Click **Browse...** next to "Livery Archive(s)" and select one or more `.zip` files containing the liveries you want to install.
    - **Select the correct Aircraft Variant** using the radio buttons (777-200ER, 777-300ER, or 777F). **This is mandatory.** If installing multiple ZIPs, they _must_ all be for this selected variant.
    - (Optional) If you selected only _one_ ZIP file, you can enter a custom name for it in the "Livery Name (in sim)" box. Otherwise, the name will be auto-detected.
    - Click **Install Livery(s) & Generate Layout**.
5.  **Check Log:** Monitor the "Installation Log" window for progress and any errors.
6.  **Restart MSFS:** If MSFS was running during the installation, restart it to see the new liveries.

## Requirements

- Windows Operating System.
- Microsoft Flight Simulator (2020).
- PMDG 777 Aircraft Package(s) installed.
- [MSFSLayoutGenerator.exe](https://github.com/HughesMDflyer4/MSFSLayoutGenerator/releases) downloaded and its path configured in the tool.
- (Optional) [.NET Desktop Runtime](https://dotnet.microsoft.com/en-us/download/dotnet/6.0) (usually version 6.0 or later) might be needed for MSFSLayoutGenerator.exe to run correctly.

## Feedback / Issues

Please report any bugs or suggest features using the [**Issues**](https://github.com/semartinezmo/PMDG-Livery-Installer/issues) tab on GitHub. Provide details from the Installation Log if reporting errors.

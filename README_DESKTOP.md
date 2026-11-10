# VELXTRIA V58.1 — Desktop installer build kit

This kit contains the full application source and packaging scripts. **It is not a precompiled Windows installer.** Build on Windows using Python 3, internet access for build dependencies, and optional [Inno Setup 6](https://jrsoftware.org/isinfo.php). End users of the resulting packaged build do not need Python or Cursor.

## Build

1. Extract the archive on Windows 10/11.
2. Install Python 3 and Inno Setup 6 on the **build machine**.
3. Double-click `BUILD_WINDOWS.bat`.
4. Find `dist\VELXTRIA-Desktop\VELXTRIA-Desktop.exe` and, if Inno Setup is available, `dist\installer\VELXTRIA-Desktop-Setup.exe`.
5. Test on a clean Windows machine before distributing. No code signing is included; SmartScreen may warn.

## What changed

- A native-feeling window via pywebview (falls back to a browser when webview is not available). Windows WebView2 may be required by the target machine.
- User-scoped Inno Setup installer with desktop and Start Menu shortcuts.
- Application data at `%LOCALAPPDATA%\VELXTRIA\Data`, preserved on uninstall and upgrade.
- Startup SQLite snapshot backup with integrity verification and 10-file retention, plus standalone `desktop_maintenance.py backup` and `desktop_maintenance.py diagnose` commands.
- Installer upgrades replace application binaries but **do not overwrite the data directory**. No network auto-updater or signature verification is implemented. Close VELXTRIA before upgrading.

## Security and limitations

- This local server listens on 127.0.0.1:8878. Other local processes may access the port; do not assume localhost alone is an authorization boundary.
- Packaging has not been validated on Windows here. WebView2, optional integrations, missing dynamically imported Python modules, and external executables may require adjustments.
- Backups are local and unencrypted. Protect your Windows account and consider encrypted off-device backups. A backup is not a guarantee of full recovery; test restores separately.
- The installer is **unsigned**, and no automatic update channel exists. The installer does not claim production security certification.
- Do not load sensitive real customer data before security review and Windows end-to-end testing.


## Build on GitHub without installing Python locally
See `START_HERE.txt`. The `windows-installer.yml` GitHub Actions workflow builds both the Windows setup EXE and portable app on a hosted Windows runner. No Windows binary is included in this source ZIP; verify the generated artifact and test it before relying on it.

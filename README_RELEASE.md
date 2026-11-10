# VELXTRIA V58.3 — Windows release candidate

**This is NOT a compiled Windows executable.** The package contains the full source and an automated Windows build, installer, and end-to-end smoke test. The executable cannot be verified until the workflow successfully runs on Windows.

## Get an actual Windows installer without installing Python or Cursor

1. Create a private GitHub repository and upload **the contents of this folder**, including `.github/workflows/windows-installer.yml`.
2. Open **Actions → Build downloadable VELXTRIA Windows installer → Run workflow**.
3. Wait for a green successful run. If red, open the failed step and fix the error; do not distribute artifacts from failed builds.
4. Download **VELXTRIA-Windows-Installer** under workflow **Artifacts** and extract it.
5. Double-click `VELXTRIA-Desktop-Setup.exe`, then launch VELXTRIA from the Start Menu.

The Windows workflow installs dependencies on its own runner, builds the PyInstaller EXE, runs the EXE smoke test, builds an Inno Setup installer, silently installs it to a temporary location, runs the **installed** EXE smoke test, and publishes SHA-256 checksums and downloadable artifacts. This is stronger validation than checking that a ZIP exists.

**Limitations:** This has not been run on a Windows runner in this session. Installer remains unsigned. It does not have an automatic updater, security audit, or a proven production deployment. Local user data is preserved across installer upgrades. Use a private repository if source is proprietary. Do not upload credentials, production databases, or secrets.

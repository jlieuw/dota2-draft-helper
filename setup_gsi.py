"""
Installs the Dota 2 GSI config file.
Run this once before launching the app.

Auto-detects the Steam installation path from the Windows registry.
Falls back to the default path if registry lookup fails.
"""
import sys
import os
from pathlib import Path

GSI_FILENAME = "gamestate_integration_drafthelper.cfg"
GSI_CONTENT = '''"drafthelper Configuration"
{
    "uri"           "http://localhost:4000/gsi"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.1"
    "heartbeat"     "30.0"
    "data"
    {
        "draft"     "1"
        "map"       "1"
        "hero"      "1"
    }
}
'''


def find_steam_path():
    """Tries to find Steam install dir from Windows registry."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
        return Path(steam_path)
    except Exception:
        pass
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
        return Path(steam_path)
    except Exception:
        pass
    return None


def get_gsi_dir() -> Path:
    steam = find_steam_path()
    if steam:
        candidate = steam / "steamapps" / "common" / "dota 2 beta" / "game" / "dota" / "cfg" / "gamestate_integration"
        if candidate.parent.exists():
            return candidate
    # Default fallback
    return Path(r"C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\dota\cfg\gamestate_integration")


def main():
    gsi_dir = get_gsi_dir()
    gsi_file = gsi_dir / GSI_FILENAME

    print(f"Installing GSI config to:\n  {gsi_file}\n")

    if not gsi_dir.parent.exists():
        print("ERROR: Dota 2 cfg directory not found.")
        print(f"Expected: {gsi_dir.parent}")
        print("\nMake sure Dota 2 is installed, then re-run this script.")
        sys.exit(1)

    gsi_dir.mkdir(parents=True, exist_ok=True)
    gsi_file.write_text(GSI_CONTENT)

    print("✓ GSI config installed successfully!")
    print("\nNext steps:")
    print("  1. Start Dota 2 (or restart it if already running)")
    print("  2. Run: run.bat")
    print("  3. Open your browser to: http://localhost:4000")


if __name__ == "__main__":
    main()

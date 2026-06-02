"""
Installs the Dota 2 GSI config file.
Run this once before launching the app.

Auto-detects the Steam installation path from the Windows registry.
Falls back to the default path if registry lookup fails.
"""
import re
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
        "draft"      "1"
        "map"        "1"
        "hero"       "1"
        "items"      "1"
        "player"     "1"
        "abilities"  "1"
    }
}
'''

# Keys that must be present in an existing config for it to be considered up-to-date.
_REQUIRED_GSI_KEYS = {"items", "player", "abilities"}


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


def _config_needs_update(gsi_file: Path) -> bool:
    """
    Returns True if the existing config is missing any required GSI data key set to "1".
    Parses active key-value pairs rather than doing a substring search so that
    commented-out or disabled keys (e.g. // "items" "0") are not counted as present.
    """
    try:
        content = gsi_file.read_text()
        # Extract all unquoted key->value pairs of the form: "key"  "value"
        # Lines starting with // are Valve's cfg comment syntax — skip them.
        active_keys: set[str] = set()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            m = re.match(r'"(\w+)"\s+"(\w+)"', stripped)
            if m and m.group(2) == "1":
                active_keys.add(m.group(1))
        return bool(_REQUIRED_GSI_KEYS - active_keys)
    except Exception:
        return True


def main():
    gsi_dir  = get_gsi_dir()
    gsi_file = gsi_dir / GSI_FILENAME

    if not gsi_dir.parent.exists():
        print("ERROR: Dota 2 cfg directory not found.")
        print(f"Expected: {gsi_dir.parent}")
        print("\nMake sure Dota 2 is installed, then re-run this script.")
        sys.exit(1)

    if gsi_file.exists() and not _config_needs_update(gsi_file):
        print("✓ GSI config is already up-to-date.")
        print(f"  {gsi_file}")
        return

    print(f"Installing GSI config to:\n  {gsi_file}\n")
    gsi_dir.mkdir(parents=True, exist_ok=True)
    gsi_file.write_text(GSI_CONTENT)

    print("✓ GSI config installed successfully!")
    print("\nNext steps:")
    print("  1. Start Dota 2 (or restart it if already running)")
    print("  2. Run: run.bat")
    print("  3. Open your browser to: http://localhost:4000")


if __name__ == "__main__":
    main()

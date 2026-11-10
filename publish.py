# publish.py — Waraqat Automatic Release & Deployment Script
import os
import sys
import subprocess
import shutil
import re

# 1. Colors & Icons for Terminal Output
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

def log_step(msg):
    print(f"\n{CYAN}==>{RESET} {msg}")

def log_success(msg):
    print(f"{GREEN}[✓]{RESET} {msg}")

def log_warn(msg):
    print(f"{YELLOW}[!]{RESET} {msg}")

def log_error(msg):
    print(f"{RED}[✗]{RESET} {msg}")

def run_cmd(cmd, error_msg="Command failed"):
    """Runs a shell command and raises error if exit code != 0."""
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        log_error(f"{error_msg}\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def get_current_version():
    """Extracts APP_VERSION from config.py."""
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return "0.3.0"

def update_version_in_config(new_ver):
    """Updates APP_VERSION in config.py."""
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    updated = re.sub(r'APP_VERSION\s*=\s*["\'][^"\']+["\']', f'APP_VERSION = "{new_ver}"', content)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(updated)
    log_success(f"Updated config.py to APP_VERSION = '{new_ver}'")

def bump_patch_version(ver_str):
    """Bumps patch version (e.g., 0.3.0 -> 0.3.1)."""
    parts = [int(p) for p in ver_str.split(".")]
    if len(parts) == 3:
        parts[2] += 1
    elif len(parts) == 2:
        parts.append(1)
    else:
        parts = [0, 3, 1]
    return ".".join(map(str, parts))

def main():
    print(f"{CYAN}===================================================={RESET}")
    print(f"{GREEN}    🚀 Waraqat — Automatic One-Click Publisher     {RESET}")
    print(f"{CYAN}===================================================={RESET}")

    current_ver = get_current_version()
    print(f"Current version in config.py: {YELLOW}v{current_ver}{RESET}")

    # Ask user for version bump or custom version
    suggested_ver = bump_patch_version(current_ver)
    try:
        user_input_ver = input(f"Enter new version [{suggested_ver}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        user_input_ver = ""

    new_version = user_input_ver if user_input_ver else suggested_ver
    new_tag = f"v{new_version}" if not new_version.startswith("v") else new_version
    new_version_clean = new_tag.lstrip("v")

    # Ask for release notes
    try:
        custom_notes = input("Enter release notes / changelog (or press Enter for default): ").strip()
    except (EOFError, KeyboardInterrupt):
        custom_notes = ""

    if not custom_notes:
        custom_notes = f"إصدار ورقات {new_tag}: تحسينات في الأداء، تحديثات لواجهة المستخدم وإصلاحات عامة."

    # Step 1: Update config.py
    log_step("Step 1: Updating version in config.py...")
    update_version_in_config(new_version_clean)

    # Step 2: Build with PyInstaller
    log_step("Step 2: Compiling Waraqat.exe with PyInstaller...")
    build_cmd = (
        'pyinstaller --noconfirm --onefile --windowed '
        '--icon=assets\\waraqat_icon.ico --name=Waraqat '
        '--add-data "assets;assets" '
        '--collect-all customtkinter '
        '--collect-all arabic_reshaper '
        '--collect-all plyer main.py'
    )
    print("Building executable (this may take 20-30 seconds)...")
    run_cmd(build_cmd, "PyInstaller build failed")
    
    dist_exe = os.path.join("dist", "Waraqat.exe")
    if not os.path.exists(dist_exe):
        log_error("dist/Waraqat.exe was not found after build!")
        sys.exit(1)

    # Copy to root
    try:
        shutil.copy2(dist_exe, "Waraqat.exe")
        log_success("Copied fresh Waraqat.exe to project root.")
    except Exception as e:
        log_warn(f"Could not copy to root (maybe currently running): {e}")

    # Step 3: Git Commit & Push
    log_step("Step 3: Committing source changes to Git...")
    run_cmd("git add .", "git add failed")
    
    commit_msg = f"release: {new_tag} - {custom_notes}"
    # Commit might return non-zero if nothing changed, which is fine
    res = subprocess.run(f'git commit -m "{commit_msg}"', shell=True, text=True, capture_output=True)
    if res.returncode == 0:
        log_success(f"Git commit created: {commit_msg}")
    else:
        log_warn("No new code changes to commit (or commit already exists).")

    log_step("Step 4: Pushing to GitHub (origin main)...")
    run_cmd("git push origin main", "git push failed")
    log_success("Pushed to GitHub main successfully.")

    # Step 5: Create GitHub Release via gh CLI
    log_step(f"Step 5: Publishing Release {new_tag} on GitHub...")
    rel_cmd = f'gh release create "{new_tag}" "{dist_exe}" --title "Waraqat {new_tag}" --notes "{custom_notes}" --latest'
    run_cmd(rel_cmd, "GitHub Release creation failed")
    log_success(f"GitHub Release {new_tag} is LIVE with Waraqat.exe attached!")

    print(f"\n{GREEN}===================================================={RESET}")
    print(f"{GREEN}🎉 ALL DONE! Your update is live for all users:{RESET}")
    print(f"👉 https://github.com/walidnajem/Waraqat/releases/tag/{new_tag}")
    print(f"{GREEN}===================================================={RESET}\n")

if __name__ == "__main__":
    main()

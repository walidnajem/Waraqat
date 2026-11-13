# publish.py — Waraqat Automatic Release & Deployment Script
import os
import re
import shutil
import subprocess
import sys
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.py")
DIST_EXE = os.path.join(ROOT, "dist", "Waraqat.exe")
ROOT_EXE = os.path.join(ROOT, "Waraqat.exe")
ASSETS_DIR = os.path.join(ROOT, "assets")
MIN_EXE_SIZE = 5 * 1024 * 1024

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


def run_cmd(cmd, error_msg="Command failed", stream=False):
    """
    Runs a command without a shell (safe for paths/notes containing quotes).
    Exits with a clear message when the command fails.
    """
    try:
        if stream:
            proc = subprocess.Popen(
                cmd,
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            output = []
            for line in proc.stdout:
                output.append(line)
                print(line, end="")
            proc.wait()
            if proc.returncode != 0:
                log_error(f"{error_msg}\n{''.join(output).strip()}")
                sys.exit(1)
            return "".join(output).strip()

        result = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            log_error(f"{error_msg}\n{details}")
            sys.exit(1)
        return (result.stdout or "").strip()
    except FileNotFoundError:
        log_error(f"{error_msg}\nCommand not found: {cmd[0]}")
        sys.exit(1)


def read_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def get_current_version():
    """Extracts APP_VERSION from config.py."""
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', read_config())
    if not match:
        log_error("Could not find APP_VERSION in config.py")
        sys.exit(1)
    return match.group(1)


def update_version_in_config(new_ver):
    """Updates APP_VERSION in config.py and returns the previous file content."""
    original = read_config()
    updated = re.sub(
        r'APP_VERSION\s*=\s*["\'][^"\']+["\']',
        f'APP_VERSION = "{new_ver}"',
        original,
        count=1,
    )
    if updated == original:
        log_error("APP_VERSION was not updated in config.py")
        sys.exit(1)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(updated)
    return original


def restore_config(original):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(original)
        log_warn("Restored config.py to the previous version after a failed build.")
    except Exception as e:
        log_error(f"Could not restore config.py: {e}")


def bump_patch_version(ver_str):
    """Bumps patch version (e.g., 0.3.0 -> 0.3.1)."""
    try:
        parts = [int(p) for p in str(ver_str).lstrip("v").split(".")]
    except (TypeError, ValueError):
        return "0.3.1"
    if len(parts) == 3:
        parts[2] += 1
    elif len(parts) == 2:
        parts.append(1)
    else:
        parts = [0, 3, 1]
    return ".".join(map(str, parts))


def parse_version(ver_str):
    try:
        return tuple(int(p) for p in ver_str.lstrip("v").split("."))
    except Exception:
        return (0,)


def preflight_checks():
    """Fails early before touching config.py or building anything."""
    log_step("Preflight checks: Git, GitHub CLI, PyInstaller and assets...")

    missing = [tool for tool in ("git", "gh") if shutil.which(tool) is None]
    if missing:
        log_error(
            f"Missing required tool(s): {', '.join(missing)}. "
            "Install Git and GitHub CLI, then try again."
        )
        sys.exit(1)

    pyinstaller = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if pyinstaller.returncode != 0:
        log_error(
            "PyInstaller is not installed for this Python interpreter. "
            "Run: pip install -r requirements-dev.txt"
        )
        sys.exit(1)

    auth = subprocess.run(
        ["gh", "auth", "status"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if auth.returncode != 0:
        log_error(
            "GitHub CLI is not authenticated. Run 'gh auth login' first.\n"
            f"{(auth.stderr or auth.stdout).strip()}"
        )
        sys.exit(1)

    branch = run_cmd(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        "Could not determine the current Git branch",
    )
    if branch != "main":
        log_error(f"Releases must be published from the 'main' branch (current: {branch}).")
        sys.exit(1)

    if not os.path.isdir(ASSETS_DIR):
        log_error("The assets folder is missing; the build would have no icon/assets.")
        sys.exit(1)

    log_success("Preflight checks passed.")


def build_command():
    """Returns the PyInstaller command as an argument list (no shell)."""
    build_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon=assets\\waraqat_icon.ico",
        "--name=Waraqat",
        "--add-data=assets;assets",
        "--collect-all", "customtkinter",
        "--collect-all", "plyer",
        "main.py",
    ]
    # winotify is an optional Windows notification fallback.
    if importlib.util.find_spec("winotify") is not None:
        build_cmd[-1:-1] = ["--collect-all", "winotify"]
    return build_cmd


def build_executable():
    """Builds dist/Waraqat.exe from the current source tree."""
    build_cmd = build_command()

    # Remove an old artifact so a failed build can never publish a stale exe.
    if os.path.exists(DIST_EXE):
        try:
            os.remove(DIST_EXE)
        except OSError as e:
            log_error(f"Could not remove the previous dist/Waraqat.exe: {e}")
            sys.exit(1)

    print("Building executable (this may take 20-30 seconds)...")
    run_cmd(build_cmd, "PyInstaller build failed", stream=True)

    if not os.path.exists(DIST_EXE):
        log_error("dist/Waraqat.exe was not found after the build!")
        sys.exit(1)

    size = os.path.getsize(DIST_EXE)
    if size < MIN_EXE_SIZE:
        log_error(
            f"dist/Waraqat.exe is suspiciously small ({size} bytes). "
            "The build may be incomplete."
        )
        sys.exit(1)

    log_success(f"Built dist/Waraqat.exe ({size / 1024 / 1024:.1f} MB).")


def main():
    print(f"{CYAN}===================================================={RESET}")
    print(f"{GREEN}    🚀 Waraqat — Automatic One-Click Publisher     {RESET}")
    print(f"{CYAN}===================================================={RESET}")

    preflight_checks()

    current_ver = get_current_version()
    print(f"Current version in config.py: {YELLOW}v{current_ver}{RESET}")

    # Ask user for version bump or custom version
    suggested_ver = bump_patch_version(current_ver)
    try:
        user_input_ver = input(f"Enter new version [{suggested_ver}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        user_input_ver = ""

    new_version = user_input_ver if user_input_ver else suggested_ver
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+)", new_version)
    if not match:
        log_error("Invalid version format. Use MAJOR.MINOR.PATCH (e.g., 0.4.4).")
        sys.exit(1)

    new_version_clean = match.group(1)
    new_tag = f"v{new_version_clean}"

    if parse_version(new_version_clean) <= parse_version(current_ver):
        log_error(
            f"The new version ({new_version_clean}) must be greater than "
            f"the current version ({current_ver})."
        )
        sys.exit(1)

    # Refuse to overwrite an existing tag/release.
    existing_tag = run_cmd(
        ["git", "tag", "--list", new_tag],
        "Could not check existing Git tags",
    )
    if existing_tag:
        log_error(f"Git tag {new_tag} already exists. Choose another version.")
        sys.exit(1)

    existing_release = subprocess.run(
        ["gh", "release", "view", new_tag],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if existing_release.returncode == 0:
        log_error(f"GitHub release {new_tag} already exists. Choose another version.")
        sys.exit(1)

    # Ask for release notes
    try:
        custom_notes = input("Enter release notes / changelog (or press Enter for default): ").strip()
    except (EOFError, KeyboardInterrupt):
        custom_notes = ""

    if not custom_notes:
        custom_notes = f"إصدار ورقات {new_tag}: تحسينات في الأداء، تحديثات لواجهة المستخدم وإصلاحات عامة."

    # Step 1: Update config.py (rolled back if the build fails).
    log_step(f"Step 1: Updating config.py to APP_VERSION = '{new_version_clean}'...")
    original_config = update_version_in_config(new_version_clean)
    log_success(f"Updated config.py to APP_VERSION = '{new_version_clean}'")

    # Step 2: Build with PyInstaller
    log_step("Step 2: Compiling Waraqat.exe with PyInstaller...")
    try:
        build_executable()
    except BaseException:
        restore_config(original_config)
        raise

    # Copy to root for local use. The release itself always uses dist\Waraqat.exe.
    try:
        shutil.copy2(DIST_EXE, ROOT_EXE)
        log_success("Copied fresh Waraqat.exe to project root.")
    except Exception as e:
        log_warn(f"Could not copy to root (maybe currently running): {e}")

    # Step 3: Git Commit & Push
    log_step("Step 3: Committing source changes to Git...")
    run_cmd(["git", "add", "-A"], "git add failed")

    commit_msg = f"release: {new_tag} - {custom_notes}"
    commit = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if commit.returncode == 0:
        log_success(f"Git commit created: {commit_msg}")
    else:
        pending = run_cmd(
            ["git", "status", "--porcelain"],
            "Could not check the Git working tree after a failed commit",
        )
        if pending:
            details = (commit.stderr or commit.stdout or "").strip()
            log_error(f"Git commit failed and changes are still pending.\n{details}")
            sys.exit(1)
        log_warn("No new code changes to commit (or commit already exists).")

    log_step("Step 4: Pushing to GitHub (origin main)...")
    run_cmd(["git", "push", "origin", "main"], "git push failed")
    log_success("Pushed to GitHub main successfully.")

    # Step 5: Create GitHub Release via gh CLI
    log_step(f"Step 5: Publishing Release {new_tag} on GitHub...")
    run_cmd(
        [
            "gh",
            "release",
            "create",
            new_tag,
            DIST_EXE,
            "--title", f"Waraqat {new_tag}",
            "--notes", custom_notes,
            "--latest",
        ],
        "GitHub Release creation failed",
    )
    log_success(f"GitHub Release {new_tag} is LIVE with Waraqat.exe attached!")

    print(f"\n{GREEN}===================================================={RESET}")
    print(f"{GREEN}🎉 ALL DONE! Your update is live for all users:{RESET}")
    print(f"👉 https://github.com/walidnajem/Waraqat/releases/tag/{new_tag}")
    print(f"{GREEN}===================================================={RESET}\n")


if __name__ == "__main__":
    main()

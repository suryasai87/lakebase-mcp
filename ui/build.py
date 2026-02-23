"""Build the UI: compile React frontend and copy to backend/static/."""
import subprocess
import shutil
from pathlib import Path

UI_DIR = Path(__file__).parent
FRONTEND_DIR = UI_DIR / "frontend"
STATIC_DIR = UI_DIR / "backend" / "static"


def build():
    print("=== Installing frontend dependencies ===")
    subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)

    print("\n=== Building frontend ===")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)

    print("\n=== Copying dist to backend/static/ ===")
    dist_dir = FRONTEND_DIR / "dist"
    if not dist_dir.exists():
        raise RuntimeError(f"Build output not found at {dist_dir}")

    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    shutil.copytree(dist_dir, STATIC_DIR)
    print(f"Frontend built and copied to {STATIC_DIR}")

    # Count files
    files = list(STATIC_DIR.rglob("*"))
    file_count = sum(1 for f in files if f.is_file())
    print(f"Total files: {file_count}")


if __name__ == "__main__":
    build()

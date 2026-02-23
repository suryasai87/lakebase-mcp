"""Deploy Lakebase MCP UI to Databricks Apps.

Uses a staging directory to avoid syncing node_modules, .git, tests, etc.

Usage:
    python ui/deploy_to_databricks.py --app-name lakebase-mcp-ui
    python ui/deploy_to_databricks.py --app-name lakebase-mcp-ui --hard-redeploy
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

UI_DIR = Path(__file__).parent
PROJECT_DIR = UI_DIR.parent  # lakebase-mcp/


def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"  STDERR: {result.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def build_staging_dir(staging: Path):
    """Copy only the files needed for the deployed app into a staging dir."""
    # 1. server/ package (governance imports)
    shutil.copytree(
        PROJECT_DIR / "server",
        staging / "server",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # 2. ui/backend/ (FastAPI app + built static files)
    shutil.copytree(
        UI_DIR / "backend",
        staging / "ui" / "backend",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # 3. ui/__init__.py
    shutil.copy2(UI_DIR / "__init__.py", staging / "ui" / "__init__.py")

    # 4. Root-level files
    shutil.copy2(PROJECT_DIR / "requirements.txt", staging / "requirements.txt")
    shutil.copy2(PROJECT_DIR / "pyproject.toml", staging / "pyproject.toml")

    # 5. UI's app.yaml as root app.yaml
    shutil.copy2(UI_DIR / "app.yaml", staging / "app.yaml")

    # Count files
    files = [f for f in staging.rglob("*") if f.is_file()]
    print(f"  Staging directory: {len(files)} files")


def deploy(app_name: str, hard_redeploy: bool = False, profile: str = "DEFAULT"):
    print(f"=== Deploying {app_name} to Databricks Apps ===\n")

    # Step 1: Build frontend
    print("Step 1/5: Building frontend...")
    subprocess.run(
        [sys.executable, str(UI_DIR / "build.py")],
        check=True,
    )

    # Step 2: Create staging directory (only needed files)
    print("\nStep 2/5: Creating staging directory...")
    staging_dir = Path(tempfile.mkdtemp(prefix="lakebase-mcp-ui-"))
    try:
        build_staging_dir(staging_dir)

        # Step 3: Create or get app
        print(f"\nStep 3/5: Ensuring app '{app_name}' exists...")
        try:
            run(["databricks", "apps", "get", app_name, "--profile", profile])
            print(f"  App '{app_name}' exists.")
            if hard_redeploy:
                print("  Hard redeploy: deleting and recreating...")
                run(["databricks", "apps", "delete", app_name, "--profile", profile])
                run(["databricks", "apps", "create", app_name, "--profile", profile])
        except RuntimeError:
            print(f"  Creating app '{app_name}'...")
            run(["databricks", "apps", "create", app_name, "--profile", profile])

        # Step 4: Sync staging directory to workspace
        print("\nStep 4/5: Syncing files to workspace...")
        workspace_path = f"/Workspace/Users/suryasai.turaga@databricks.com/{app_name}"
        run([
            "databricks", "workspace", "import-dir",
            str(staging_dir), workspace_path,
            "--overwrite",
            "--profile", profile,
        ])

        # Step 5: Deploy
        print("\nStep 5/5: Deploying app...")
        output = run([
            "databricks", "apps", "deploy", app_name,
            "--source-code-path", workspace_path,
            "--profile", profile,
        ])
        print(f"\n{output}")
        print(f"\n=== Deployment complete! ===")

    finally:
        # Clean up staging directory
        shutil.rmtree(staging_dir, ignore_errors=True)
        print("  Cleaned up staging directory.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Lakebase MCP UI")
    parser.add_argument("--app-name", required=True, help="Databricks app name")
    parser.add_argument("--hard-redeploy", action="store_true", help="Delete and recreate app")
    parser.add_argument("--profile", default="DEFAULT", help="Databricks CLI profile")
    args = parser.parse_args()
    deploy(args.app_name, args.hard_redeploy, args.profile)

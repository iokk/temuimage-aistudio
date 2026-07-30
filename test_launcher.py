import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent
LAUNCHER = REPOSITORY_ROOT / "启动TuLite.command"


class LauncherTests(unittest.TestCase):
    def make_probe_runtime(self, root: Path, streamlit_version="1.50.0", omit=""):
        packages = root / "packages"
        packages.mkdir()
        modules = {
            "streamlit.py": f'__version__ = "{streamlit_version}"\n',
            "PIL/__init__.py": "",
            "google/__init__.py": "",
            "google/genai/__init__.py": "",
            "httpx.py": "",
            "socksio.py": "",
            "boto3.py": "",
            "webview.py": "",
            "cryptography.py": "",
        }
        for relative, content in modules.items():
            if relative.split("/", 1)[0].removesuffix(".py") == omit:
                continue
            path = packages / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        bin_directory = root / "bin"
        bin_directory.mkdir()
        python = bin_directory / "python3"
        python.write_text(
            "#!/bin/sh\nexec /usr/bin/python3 -S \"$@\"\n", encoding="utf-8"
        )
        python.chmod(0o755)
        return packages, bin_directory

    def run_probe(self, streamlit_version="1.50.0", omit=""):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        shutil.copy2(LAUNCHER, root / LAUNCHER.name)
        packages, bin_directory = self.make_probe_runtime(
            root, streamlit_version=streamlit_version, omit=omit
        )
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": str(bin_directory) + os.pathsep + environment.get("PATH", ""),
                "PYTHONPATH": str(packages),
                "TULITE_DEPENDENCY_PROBE_ONLY": "1",
            }
        )
        return root, subprocess.run(
            ["/bin/bash", str(root / LAUNCHER.name)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_dependency_probe_rejects_old_streamlit_and_missing_runtime_import(self):
        _, old_streamlit = self.run_probe(streamlit_version="1.49.9")
        _, missing_boto3 = self.run_probe(omit="boto3")
        _, missing_socksio = self.run_probe(omit="socksio")
        _, valid = self.run_probe()

        self.assertNotEqual(old_streamlit.returncode, 0)
        self.assertNotEqual(missing_boto3.returncode, 0)
        self.assertNotEqual(missing_socksio.returncode, 0)
        self.assertEqual(valid.returncode, 0, valid.stderr)

    def test_launcher_preserves_existing_git_lock(self):
        root, result = self.run_probe()
        lock = root / ".git" / "index.lock"
        lock.parent.mkdir()
        lock.write_text("existing lock", encoding="utf-8")

        result = subprocess.run(
            ["/bin/bash", str(root / LAUNCHER.name)],
            cwd=root,
            env={
                **os.environ,
                "PATH": str(root / "bin") + os.pathsep + os.environ.get("PATH", ""),
                "PYTHONPATH": str(root / "packages"),
                "TULITE_DEPENDENCY_PROBE_ONLY": "1",
            },
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(lock.read_text(encoding="utf-8"), "existing lock")


if __name__ == "__main__":
    unittest.main(verbosity=2)

import os
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent


def copy_explicit_python_files(dockerfile: Path, image_root: Path) -> None:
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().upper().startswith("COPY "):
            continue
        parts = shlex.split(line, comments=True)
        if len(parts) != 3:
            raise AssertionError(f"unsupported COPY instruction: {line}")

        source_text, destination_text = parts[1:]
        source = REPOSITORY_ROOT / source_text
        if source.suffix != ".py" or not source.is_file():
            continue

        destination = Path(destination_text)
        if destination_text.endswith("/") or destination_text in {".", "./"}:
            destination /= source.name
        target = image_root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class DeploymentManifestTests(unittest.TestCase):
    def test_dockerfiles_copy_suite_runtime_modules(self):
        required_sources = {"suite_planner.py", "suite_output.py"}

        for dockerfile_name in ("Dockerfile", "Dockerfile.web"):
            with self.subTest(dockerfile=dockerfile_name):
                copied_sources = {
                    shlex.split(line, comments=True)[1]
                    for line in (REPOSITORY_ROOT / dockerfile_name)
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.lstrip().upper().startswith("COPY ")
                }

                self.assertTrue(
                    required_sources.issubset(copied_sources),
                    f"{dockerfile_name} must copy the suite runtime modules",
                )

    def test_web_requirements_include_encrypted_secret_storage(self):
        requirements = {
            re.split(r"[<>=!~]", line, maxsplit=1)[0].strip().lower()
            for line in (REPOSITORY_ROOT / "requirements-web.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("cryptography", requirements)

    def test_compose_files_render_authentication_and_encryption_environment(self):
        environment = os.environ.copy()
        environment.update(
            {
                "APP_ACCESS_PASSWORD": "acceptance-password",
                "XIAOBAITU_SECRET_KEY": "acceptance-fernet-key",
            }
        )
        compose_files = [
            REPOSITORY_ROOT / "docker-compose.yml",
            REPOSITORY_ROOT / "deploy/1panel/docker-compose.yml",
        ]

        for compose_file in compose_files:
            with self.subTest(compose=str(compose_file)):
                docker = shutil.which("docker")
                rendered = ""
                if docker:
                    result = subprocess.run(
                        [
                            docker,
                            "compose",
                            "-f",
                            str(compose_file),
                            "config",
                            "--format",
                            "json",
                        ],
                        cwd=REPOSITORY_ROOT,
                        env=environment,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        rendered = result.stdout
                if rendered:
                    configuration = json.loads(rendered)
                    service = next(iter(configuration["services"].values()))
                    self.assertEqual(
                        service["environment"]["APP_ACCESS_PASSWORD"],
                        "acceptance-password",
                    )
                    self.assertEqual(
                        service["environment"]["XIAOBAITU_SECRET_KEY"],
                        "acceptance-fernet-key",
                    )
                    self.assertEqual(service["ports"][0]["host_ip"], "127.0.0.1")
                else:
                    structure = compose_file.read_text(encoding="utf-8")
                    self.assertIn(
                        "APP_ACCESS_PASSWORD: ${APP_ACCESS_PASSWORD:?", structure
                    )
                    self.assertIn(
                        "XIAOBAITU_SECRET_KEY: ${XIAOBAITU_SECRET_KEY:-}", structure
                    )
                    self.assertIn("${APP_BIND_ADDRESS:-127.0.0.1}", structure)

                if docker:
                    without_password = environment.copy()
                    without_password.pop("APP_ACCESS_PASSWORD", None)
                    with tempfile.NamedTemporaryFile() as empty_environment:
                        missing_password = subprocess.run(
                            [
                                docker,
                                "compose",
                                "--env-file",
                                empty_environment.name,
                                "-f",
                                str(compose_file),
                                "config",
                                "-q",
                            ],
                            cwd=REPOSITORY_ROOT,
                            env=without_password,
                            capture_output=True,
                            text=True,
                        )
                    self.assertNotEqual(missing_password.returncode, 0)
                    self.assertIn(
                        "APP_ACCESS_PASSWORD",
                        missing_password.stderr + missing_password.stdout,
                    )

        for example_path in (
            REPOSITORY_ROOT / ".env.example",
            REPOSITORY_ROOT / "deploy/1panel/.env.example",
        ):
            with self.subTest(example=str(example_path)):
                example = example_path.read_text(encoding="utf-8")
                password_lines = [
                    line
                    for line in example.splitlines()
                    if line.startswith("APP_ACCESS_PASSWORD=")
                ]
                self.assertEqual(
                    password_lines,
                    ["APP_ACCESS_PASSWORD="],
                )
                self.assertIn("APP_BIND_ADDRESS=127.0.0.1", example)
                self.assertIn("XIAOBAITU_SECRET_KEY=", example)

    def test_local_streamlit_default_binds_only_to_loopback(self):
        from streamlit import config

        self.assertEqual(config.get_option("server.address"), "127.0.0.1")

    def test_onepanel_guide_requires_complete_docker_build_context(self):
        guide = (REPOSITORY_ROOT / "deploy/1panel/README.md").read_text(
            encoding="utf-8"
        )

        for required in (
            "完整仓库",
            "task_engine.py",
            "task_store.py",
            "task_status.py",
            "run_tulite.py",
            "provider_acceptance.py",
            "scripts/verify_provider.py",
            ".streamlit/",
        ):
            self.assertIn(required, guide)

    def test_install_and_update_validate_compose_before_side_effects(self):
        for action in ("install", "update"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temporary_directory:
                deployment_root = Path(temporary_directory)
                shutil.copy2(
                    REPOSITORY_ROOT / "deploy.sh",
                    deployment_root / "deploy.sh",
                )
                shutil.copy2(
                    REPOSITORY_ROOT / ".env.example",
                    deployment_root / ".env.example",
                )
                fake_bin = deployment_root / "bin"
                fake_bin.mkdir()
                docker_log = deployment_root / "docker.log"
                fake_docker = fake_bin / "docker"
                fake_docker.write_text(
                    "#!/bin/sh\n"
                    'printf "%s\\n" "$*" >> "$DOCKER_LOG"\n'
                    'if [ "$*" = "compose version" ]; then exit 0; fi\n'
                    'if [ "$*" = "compose config --quiet" ]; then exit 7; fi\n'
                    'if [ "$*" = "compose up -d" ]; then exit 7; fi\n'
                    "exit 0\n",
                    encoding="utf-8",
                )
                fake_docker.chmod(0o755)
                environment = os.environ.copy()
                environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
                environment["DOCKER_LOG"] = str(docker_log)

                result = subprocess.run(
                    ["/bin/bash", "deploy.sh", action],
                    cwd=deployment_root,
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                commands = docker_log.read_text(encoding="utf-8").splitlines()

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("compose config --quiet", commands)
                self.assertNotIn("compose down", commands)
                self.assertNotIn("compose build --no-cache", commands)

    def test_windows_deploy_validates_compose_before_starting(self):
        lines = [
            line.strip()
            for line in (REPOSITORY_ROOT / "deploy.bat")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertIn("docker compose version >nul 2>&1", lines)
        self.assertIn("docker compose config --quiet", lines)
        self.assertIn("docker compose up -d --build", lines)
        version_index = lines.index("docker compose version >nul 2>&1")
        config_index = lines.index("docker compose config --quiet")
        start_index = lines.index("docker compose up -d --build")

        self.assertLess(version_index, config_index)
        self.assertLess(config_index, start_index)
        config_failure_block = "\n".join(lines[config_index:start_index])
        self.assertIn(".env", config_failure_block)
        self.assertIn("APP_ACCESS_PASSWORD", config_failure_block)

    def test_dockerfiles_run_from_only_their_explicit_python_copies(self):
        for dockerfile_name in ("Dockerfile", "Dockerfile.web"):
            with self.subTest(dockerfile=dockerfile_name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    image_root = Path(temporary_directory)
                    copy_explicit_python_files(
                        REPOSITORY_ROOT / dockerfile_name,
                        image_root,
                    )
                    environment = os.environ.copy()
                    environment.pop("PYTHONPATH", None)
                    environment.update(
                        {
                            "APP_RUNTIME": "server",
                            "ECOMMERCE_WORKBENCH_DATA_DIR": str(
                                image_root / "data"
                            ),
                            "ECOMMERCE_WORKBENCH_PROJECTS_DIR": str(
                                image_root / "data" / "projects"
                            ),
                            "FILE_STORAGE_PATH": str(
                                image_root / "data" / "files"
                            ),
                        }
                    )

                    imports = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            (
                                "import app, task_engine, task_store, "
                                "task_status, run_tulite"
                            ),
                        ],
                        cwd=image_root,
                        env=environment,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        imports.returncode,
                        0,
                        f"{dockerfile_name} isolated imports failed:\n"
                        f"stdout:\n{imports.stdout}\n"
                        f"stderr:\n{imports.stderr}",
                    )

                    provider_help = subprocess.run(
                        [
                            sys.executable,
                            "scripts/verify_provider.py",
                            "--help",
                        ],
                        cwd=image_root,
                        env=environment,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        provider_help.returncode,
                        0,
                        f"{dockerfile_name} provider help failed:\n"
                        f"stdout:\n{provider_help.stdout}\n"
                        f"stderr:\n{provider_help.stderr}",
                    )
                    self.assertIn("--provider-id", provider_help.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

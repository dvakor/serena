"""
Provides BSL (1C:Enterprise) specific instantiation of the LanguageServer class.
Contains various configurations and settings specific to BSL/OneScript.

BSL Language Server provides support for:
- 1C:Enterprise 8 source files (*.bsl)
- OneScript files (*.os)

You can configure the following options in ls_specific_settings (in serena_config.yml):

    ls_specific_settings:
      bsl:
        memory: '8G'           # JVM memory limit (default: 4G). Takes priority over jvm_options -Xmx.
        version: '0.28.0'      # Pin specific version (optional, disables auto-updates)
        jvm_options: '-XX:+UseG1GC'  # Additional JVM options (default: none)

Memory setting priority:
1. Explicit `memory` setting (e.g., '8G')
2. -Xmx value extracted from `jvm_options` (for backward compatibility)
3. Default: '4G'

Auto-update behavior:
- By default, BSL LS automatically downloads new versions in the background
- Updates are staged and applied on next startup (no interruption to current session)
- Update checks happen at most once per hour
- Set `version` to pin a specific version and disable auto-updates

Example configuration:

    ls_specific_settings:
      bsl:
        memory: '8G'
        jvm_options: '-XX:+UseG1GC -XX:MaxGCPauseMillis=200'

Example with version pinning (disables auto-updates):

    ls_specific_settings:
      bsl:
        memory: '4G'
        version: '0.28.0'

Note: Language for diagnostics can be configured via .bsl-language-server.json file in project root.
If .bsl-language-server.json exists in project root, it will be automatically detected and passed
to the language server with the -c flag.
"""

import dataclasses
import json
import logging
import os
import pathlib
import re
import shutil
import stat
import sys
import threading
import urllib.request
from datetime import UTC, datetime
from typing import IO, Any, cast

# Cross-platform file locking
# Note: Uses file-based locking for inter-process synchronization during updates.
# On Windows, locks the first 1024 bytes; on Unix, uses flock for whole-file locking.
if sys.platform == "win32":
    import msvcrt

    _LOCK_SIZE = 1024  # Bytes to lock on Windows

    def _lock_file(fd: IO[str]) -> bool:
        """Acquire exclusive lock on file (Windows). Locks first 1024 bytes."""
        try:
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, _LOCK_SIZE)
            return True
        except OSError:
            return False

    def _unlock_file(fd: IO[str]) -> None:
        """Release lock on file (Windows)."""
        try:
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, _LOCK_SIZE)
        except OSError:
            pass

else:
    import fcntl

    def _lock_file(fd: IO[str]) -> bool:
        """Acquire exclusive lock on file (Unix). Uses flock for whole-file locking."""
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def _unlock_file(fd: IO[str]) -> None:
        """Release lock on file (Unix)."""
        fcntl.flock(fd, fcntl.LOCK_UN)


from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)

# Default memory setting for BSL Language Server (used when no explicit memory is configured)
DEFAULT_BSL_MEMORY = "4G"

# BSL Language Server configuration file name
BSL_CONFIG_FILENAME = ".bsl-language-server.json"

# GitHub API URL for latest release
BSL_LS_GITHUB_API_URL = "https://api.github.com/repos/1c-syntax/bsl-language-server/releases/latest"

# GitHub API URL for all releases (used for version pinning)
BSL_LS_GITHUB_RELEASES_URL = "https://api.github.com/repos/1c-syntax/bsl-language-server/releases"

# Minimum interval between update checks (in seconds) - 1 hour
UPDATE_CHECK_INTERVAL_SECONDS = 3600

# Version file name
VERSION_FILENAME = "version.json"

# Staged directory name
STAGED_DIR_NAME = ".staged"

# Lock file name for concurrent access
LOCK_FILENAME = ".update.lock"


@dataclasses.dataclass
class VersionInfo:
    """
    Stores version metadata for BSL Language Server.

    Attributes:
        current: Currently active version (e.g., "0.28.0")
        staged: Downloaded but not yet activated version (e.g., "0.29.0"), or None
        last_check: ISO 8601 timestamp of last update check, or None
        pinned: Pinned version if set in config, or None

    """

    current: str | None = None
    staged: str | None = None
    last_check: str | None = None
    pinned: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "current": self.current,
            "staged": self.staged,
            "last_check": self.last_check,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionInfo":
        """Create VersionInfo from dictionary."""
        return cls(
            current=data.get("current"),
            staged=data.get("staged"),
            last_check=data.get("last_check"),
            pinned=data.get("pinned"),
        )


@dataclasses.dataclass
class BslRuntimeDependencyPaths:
    """
    Stores the paths to the runtime dependencies of BSL Language Server
    """

    java_path: str
    java_home_path: str
    bsl_jar_path: str


class BslLanguageServer(SolidLanguageServer):
    """
    Provides BSL (1C:Enterprise/OneScript) specific instantiation of the LanguageServer class.
    Contains various configurations and settings specific to BSL.
    """

    def __init__(self, config: LanguageServerConfig, repository_root_path: str, solidlsp_settings: SolidLSPSettings):
        """
        Creates a BSL Language Server instance.
        This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        runtime_dependency_paths = self._setup_runtime_dependencies(config, solidlsp_settings)
        self.runtime_dependency_paths = runtime_dependency_paths

        # Get memory setting using priority: explicit memory > jvm_options -Xmx > default
        memory_setting = self._get_memory_setting(solidlsp_settings)

        # Build JVM options with memory setting
        jvm_args = [f"-Xmx{memory_setting}"]

        # Add additional JVM options if specified (excluding -Xmx which we already handle)
        if solidlsp_settings.ls_specific_settings:
            bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
            custom_jvm_options = bsl_settings.get("jvm_options", "")
            if custom_jvm_options:
                # Filter out -Xmx flags since we handle memory separately
                filtered_options = re.sub(r"-Xmx\d+[GgMm]?\s*", "", custom_jvm_options).strip()
                if filtered_options:
                    jvm_args.extend(filtered_options.split())
                    log.info(f"Using additional JVM options for BSL Language Server: {filtered_options}")

        log.info(f"BSL Language Server JVM args: {jvm_args}")

        # Build command to run BSL Language Server
        # Note: BSL LS in LSP mode doesn't accept --language flag, it's only for analyzer mode
        # Language configuration is done via .bsl-language-server.json config file
        cmd = [
            self.runtime_dependency_paths.java_path,
            *jvm_args,
            "-jar",
            self.runtime_dependency_paths.bsl_jar_path,
        ]

        # Add config file path if .bsl-language-server.json exists
        config_file_path = self._find_config_file(repository_root_path)
        if config_file_path:
            cmd.extend(["-c", config_file_path])

        # Set environment variables including JAVA_HOME
        proc_env = {
            "JAVA_HOME": self.runtime_dependency_paths.java_home_path,
        }

        super().__init__(
            config, repository_root_path, ProcessLaunchInfo(cmd=cmd, env=proc_env, cwd=repository_root_path), "bsl", solidlsp_settings
        )

    @staticmethod
    def _get_memory_setting(solidlsp_settings: SolidLSPSettings) -> str:
        """
        Extract memory setting from configuration.

        Priority:
        1. Explicit `memory` setting in ls_specific_settings.bsl
        2. Extract from `jvm_options` if contains -Xmx flag
        3. Default: DEFAULT_BSL_MEMORY (4G)

        Args:
            solidlsp_settings: The SolidLSP settings object

        Returns:
            Memory value as string (e.g., "4G", "8G")

        """
        if not solidlsp_settings.ls_specific_settings:
            return DEFAULT_BSL_MEMORY

        bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)

        # Priority 1: Explicit memory setting
        explicit_memory = bsl_settings.get("memory", "")
        if explicit_memory:
            log.info(f"Using explicit memory setting for BSL Language Server: {explicit_memory}")
            return explicit_memory

        # Priority 2: Extract from jvm_options if present
        jvm_options = bsl_settings.get("jvm_options", "")
        if jvm_options:
            match = re.search(r"-Xmx(\d+[GgMm]?)", jvm_options)
            if match:
                memory_value = match.group(1)
                log.info(f"Extracted memory from jvm_options for BSL Language Server: {memory_value}")
                return memory_value

        # Priority 3: Default
        return DEFAULT_BSL_MEMORY

    @staticmethod
    def _find_config_file(repository_root_path: str) -> str | None:
        """
        Locate .bsl-language-server.json configuration file in project root.

        Args:
            repository_root_path: The root path of the project

        Returns:
            Absolute path to config file if exists, None otherwise

        """
        config_path = os.path.join(repository_root_path, BSL_CONFIG_FILENAME)
        if os.path.isfile(config_path):
            log.info(f"Found BSL Language Server config file: {config_path}")
            return config_path
        return None

    @classmethod
    def _get_latest_bsl_release_url(cls) -> tuple[str, str]:
        """
        Fetches the latest release URL from GitHub API.

        Returns:
            Tuple of (download_url, version)

        """
        log.info("Fetching latest BSL Language Server release from GitHub...")

        request = urllib.request.Request(
            BSL_LS_GITHUB_API_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Serena-SolidLSP",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            release_data = json.loads(response.read().decode("utf-8"))

        version = release_data.get("tag_name", "unknown")
        assets = release_data.get("assets", [])

        # Find the executable JAR (ends with -exec.jar)
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith("-exec.jar"):
                download_url = asset.get("browser_download_url")
                log.info(f"Found BSL Language Server {version}: {name}")
                return download_url, version

        raise RuntimeError("Could not find BSL Language Server executable JAR in latest release")

    @classmethod
    def _get_release_url_for_version(cls, version: str) -> tuple[str, str] | None:
        """
        Fetches the release URL for a specific version from GitHub API.

        Args:
            version: The version to fetch (e.g., "0.28.0" or "v0.28.0")

        Returns:
            Tuple of (download_url, version) if found, None otherwise

        """
        # Normalize version - ensure it has 'v' prefix for comparison
        normalized_version = version if version.startswith("v") else f"v{version}"

        log.info(f"Fetching BSL Language Server release {normalized_version} from GitHub...")

        request = urllib.request.Request(
            BSL_LS_GITHUB_RELEASES_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Serena-SolidLSP",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                releases = json.loads(response.read().decode("utf-8"))

            for release in releases:
                tag = release.get("tag_name", "")
                if tag in (normalized_version, version):
                    assets = release.get("assets", [])
                    for asset in assets:
                        name = asset.get("name", "")
                        if name.endswith("-exec.jar"):
                            download_url = asset.get("browser_download_url")
                            log.info(f"Found BSL Language Server {tag}: {name}")
                            return download_url, tag
        except Exception as e:
            log.warning(f"Failed to fetch release {version}: {e}")

        return None

    @classmethod
    def _read_version_info(cls, static_dir: str) -> VersionInfo:
        """
        Read version information from version.json file.

        Args:
            static_dir: Path to the BSL Language Server static directory

        Returns:
            VersionInfo object with current version metadata

        """
        version_file = os.path.join(static_dir, VERSION_FILENAME)
        if os.path.exists(version_file):
            try:
                with open(version_file, encoding="utf-8") as f:
                    data = json.load(f)
                return VersionInfo.from_dict(data)
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Failed to read version.json: {e}")
        return VersionInfo()

    @classmethod
    def _write_version_info(cls, static_dir: str, version_info: VersionInfo) -> None:
        """
        Write version information to version.json file.

        Args:
            static_dir: Path to the BSL Language Server static directory
            version_info: VersionInfo object to write

        """
        version_file = os.path.join(static_dir, VERSION_FILENAME)
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                json.dump(version_info.to_dict(), f, indent=2)
        except OSError as e:
            log.warning(f"Failed to write version.json: {e}")

    @classmethod
    def _extract_version_from_jar_name(cls, jar_name: str) -> str | None:
        """
        Extract version from JAR filename.

        Args:
            jar_name: JAR filename (e.g., "bsl-language-server-0.28.0-exec.jar")

        Returns:
            Version string (e.g., "v0.28.0") or None if not found

        """
        # Pattern: bsl-language-server-X.Y.Z-exec.jar
        match = re.search(r"bsl-language-server-(\d+\.\d+\.\d+)-exec\.jar", jar_name)
        if match:
            return f"v{match.group(1)}"
        return None

    @classmethod
    def _apply_staged_version(cls, static_dir: str, bsl_dir: str) -> str | None:
        """
        Apply staged version if exists, making it the active version.

        This method is called at startup to activate a previously downloaded update.
        It moves the staged JAR to the main directory and removes the old version.

        Args:
            static_dir: Path to the BSL Language Server static directory
            bsl_dir: Path to the bsl-ls directory containing JAR files

        Returns:
            Path to the activated JAR file, or None if no staged version exists

        """
        staged_dir = os.path.join(bsl_dir, STAGED_DIR_NAME)
        lock_file = os.path.join(static_dir, LOCK_FILENAME)

        if not os.path.exists(staged_dir):
            return None

        staged_jars = [f for f in os.listdir(staged_dir) if f.endswith("-exec.jar")]
        if not staged_jars:
            return None

        staged_jar_name = staged_jars[0]
        staged_jar_path = os.path.join(staged_dir, staged_jar_name)

        # Use file locking for safe concurrent access
        try:
            with open(lock_file, "w") as lock_fd:
                if not _lock_file(lock_fd):
                    log.warning("Could not acquire lock for applying staged version - another process may be updating")
                    return None
                try:
                    # Find and remove existing JARs in main directory
                    existing_jars = [f for f in os.listdir(bsl_dir) if f.endswith("-exec.jar")]
                    for old_jar in existing_jars:
                        old_jar_path = os.path.join(bsl_dir, old_jar)
                        try:
                            os.remove(old_jar_path)
                            log.info(f"Removed old BSL Language Server JAR: {old_jar}")
                        except OSError as e:
                            log.warning(f"Failed to remove old JAR {old_jar}: {e}")

                    # Move staged JAR to main directory
                    target_jar_path = os.path.join(bsl_dir, staged_jar_name)
                    shutil.move(staged_jar_path, target_jar_path)

                    # Update version info
                    version_info = cls._read_version_info(static_dir)
                    staged_version = cls._extract_version_from_jar_name(staged_jar_name)
                    version_info.current = staged_version
                    version_info.staged = None
                    cls._write_version_info(static_dir, version_info)

                    log.info(f"Applied staged BSL Language Server version: {staged_version}")

                    # Clean up staged directory
                    try:
                        shutil.rmtree(staged_dir)
                    except OSError:
                        pass

                    return target_jar_path
                finally:
                    _unlock_file(lock_fd)
        except OSError as e:
            log.warning(f"Failed to apply staged version: {e}")
            return None

    @classmethod
    def _get_pinned_or_latest_version(cls, solidlsp_settings: SolidLSPSettings, static_dir: str) -> tuple[str | None, str | None, bool]:
        """
        Determine the target version based on pinning configuration.

        Args:
            solidlsp_settings: The SolidLSP settings object
            static_dir: Path to the BSL Language Server static directory

        Returns:
            Tuple of (download_url, version, is_pinned):
            - download_url: URL to download the JAR from, or None if using existing
            - version: Target version string
            - is_pinned: True if version is pinned (skip auto-updates)

        """
        bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
        pinned_version = bsl_settings.get("version")

        if pinned_version:
            # Version is pinned - try to get the specific version
            log.info(f"BSL Language Server version pinned to: {pinned_version}")

            # Update version info with pinned setting
            version_info = cls._read_version_info(static_dir)
            version_info.pinned = pinned_version
            cls._write_version_info(static_dir, version_info)

            result = cls._get_release_url_for_version(pinned_version)
            if result:
                return result[0], result[1], True
            else:
                log.warning(f"Pinned version {pinned_version} not found, falling back to latest")

        # Get latest version
        try:
            download_url, version = cls._get_latest_bsl_release_url()
            return download_url, version, pinned_version is not None
        except Exception as e:
            log.warning(f"Failed to get latest BSL Language Server release: {e}")
            return None, None, pinned_version is not None

    @classmethod
    def _should_check_for_updates(cls, version_info: VersionInfo) -> bool:
        """
        Determine if we should check for updates based on last check time.

        Args:
            version_info: Current version info

        Returns:
            True if update check should be performed

        """
        if version_info.pinned:
            return False

        if not version_info.last_check:
            return True

        try:
            last_check = datetime.fromisoformat(version_info.last_check.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            elapsed = (now - last_check).total_seconds()
            return elapsed >= UPDATE_CHECK_INTERVAL_SECONDS
        except (ValueError, TypeError):
            return True

    @classmethod
    def _start_background_update_check(cls, current_version: str | None, static_dir: str, bsl_dir: str) -> None:
        """
        Start a background thread to check for and download updates.

        Args:
            current_version: Currently installed version
            static_dir: Path to the BSL Language Server static directory
            bsl_dir: Path to the bsl-ls directory containing JAR files

        """
        version_info = cls._read_version_info(static_dir)

        if not cls._should_check_for_updates(version_info):
            log.debug("Skipping update check - not enough time since last check or version is pinned")
            return

        thread = threading.Thread(
            target=cls._check_and_download_update,
            args=(current_version, static_dir, bsl_dir),
            daemon=True,
            name="BSL-LS-UpdateChecker",
        )
        thread.start()
        log.debug("Started background update check thread for BSL Language Server")

    @classmethod
    def _check_and_download_update(cls, current_version: str | None, static_dir: str, bsl_dir: str) -> None:
        """
        Check for updates and download new version to staged directory if available.

        This method runs in a background thread and downloads updates without
        interrupting the current session. The update will be applied at next startup.

        Args:
            current_version: Currently installed version
            static_dir: Path to the BSL Language Server static directory
            bsl_dir: Path to the bsl-ls directory containing JAR files

        """
        lock_file = os.path.join(static_dir, LOCK_FILENAME)

        try:
            # Get latest version info first (outside lock - read-only operation)
            download_url, latest_version = cls._get_latest_bsl_release_url()

            # Normalize versions for comparison
            current_normalized = current_version.lstrip("v") if current_version else None
            latest_normalized = latest_version.lstrip("v") if latest_version else None

            if current_normalized == latest_normalized:
                log.debug(f"BSL Language Server is up to date: {current_version}")
                # Update last_check even when up to date (inside lock for thread safety)
                with open(lock_file, "w") as lock_fd:
                    if _lock_file(lock_fd):
                        try:
                            version_info = cls._read_version_info(static_dir)
                            version_info.last_check = datetime.now(UTC).isoformat()
                            cls._write_version_info(static_dir, version_info)
                        finally:
                            _unlock_file(lock_fd)
                return

            log.info(f"New BSL Language Server version available: {latest_version} (current: {current_version})")

            # Acquire lock for staged operations and version info updates
            with open(lock_file, "w") as lock_fd:
                if not _lock_file(lock_fd):
                    log.warning("Could not acquire lock for update download - another process may be updating")
                    return

                try:
                    # Update last check time (inside lock for thread safety)
                    version_info = cls._read_version_info(static_dir)
                    version_info.last_check = datetime.now(UTC).isoformat()
                    cls._write_version_info(static_dir, version_info)

                    # Create staged directory
                    staged_dir = os.path.join(bsl_dir, STAGED_DIR_NAME)
                    os.makedirs(staged_dir, exist_ok=True)

                    # Clean up any stale .tmp files from previous interrupted downloads
                    for f in os.listdir(staged_dir):
                        if f.endswith(".tmp"):
                            try:
                                os.remove(os.path.join(staged_dir, f))
                            except OSError:
                                pass

                    # Download to temp file first, then rename
                    jar_name = os.path.basename(download_url)
                    staged_jar_path = os.path.join(staged_dir, jar_name)
                    temp_jar_path = staged_jar_path + ".tmp"

                    log.info(f"Downloading BSL Language Server {latest_version} to staged directory...")
                    FileUtils.download_and_extract_archive(download_url, temp_jar_path, "binary")

                    # Verify download succeeded (check file exists and has reasonable size)
                    # BSL LS JAR is typically ~60MB, but we use 1MB as minimum to catch clearly corrupt files
                    min_jar_size = 1024 * 1024  # 1MB minimum
                    if os.path.exists(temp_jar_path) and os.path.getsize(temp_jar_path) > min_jar_size:
                        # Rename from .tmp to final name
                        shutil.move(temp_jar_path, staged_jar_path)

                        # Update version info with staged version
                        version_info = cls._read_version_info(static_dir)
                        version_info.staged = latest_version
                        cls._write_version_info(static_dir, version_info)

                        log.info(f"BSL Language Server {latest_version} downloaded and staged for next startup")
                    else:
                        log.warning("Downloaded JAR file appears to be corrupted or too small")
                        if os.path.exists(temp_jar_path):
                            os.remove(temp_jar_path)
                finally:
                    _unlock_file(lock_fd)

        except urllib.error.URLError as e:
            log.warning(f"Update check failed - GitHub not accessible: {e}")
        except Exception as e:
            log.warning(f"Update check failed: {e}")

    @classmethod
    def _setup_runtime_dependencies(cls, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings) -> BslRuntimeDependencyPaths:
        """
        Setup runtime dependencies for BSL Language Server and return the paths.
        """
        platform_id = PlatformUtils.get_platform_id()

        # Java runtime dependencies (same as Kotlin Language Server)
        java_dependencies = {
            "win-x64": {
                "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-win32-x64-1.42.0-561.vsix",
                "archiveType": "zip",
                "java_home_path": "extension/jre/21.0.7-win32-x86_64",
                "java_path": "extension/jre/21.0.7-win32-x86_64/bin/java.exe",
            },
            "linux-x64": {
                "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-x64-1.42.0-561.vsix",
                "archiveType": "zip",
                "java_home_path": "extension/jre/21.0.7-linux-x86_64",
                "java_path": "extension/jre/21.0.7-linux-x86_64/bin/java",
            },
            "linux-arm64": {
                "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-arm64-1.42.0-561.vsix",
                "archiveType": "zip",
                "java_home_path": "extension/jre/21.0.7-linux-aarch64",
                "java_path": "extension/jre/21.0.7-linux-aarch64/bin/java",
            },
            "osx-x64": {
                "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-x64-1.42.0-561.vsix",
                "archiveType": "zip",
                "java_home_path": "extension/jre/21.0.7-macosx-x86_64",
                "java_path": "extension/jre/21.0.7-macosx-x86_64/bin/java",
            },
            "osx-arm64": {
                "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-arm64-1.42.0-561.vsix",
                "archiveType": "zip",
                "java_home_path": "extension/jre/21.0.7-macosx-aarch64",
                "java_path": "extension/jre/21.0.7-macosx-aarch64/bin/java",
            },
        }

        # Verify platform support
        if platform_id.value not in java_dependencies:
            raise RuntimeError(f"Platform {platform_id.value} is not supported for BSL Language Server")

        java_dependency = java_dependencies[platform_id.value]

        # Setup paths for dependencies
        static_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "bsl_language_server")
        os.makedirs(static_dir, exist_ok=True)

        # Setup Java paths
        java_dir = os.path.join(static_dir, "java")
        os.makedirs(java_dir, exist_ok=True)

        java_home_path = os.path.join(java_dir, java_dependency["java_home_path"])
        java_path = os.path.join(java_dir, java_dependency["java_path"])

        # Download and extract Java if not exists
        if not os.path.exists(java_path):
            log.info(f"Downloading Java for {platform_id.value}...")
            FileUtils.download_and_extract_archive(java_dependency["url"], java_dir, java_dependency["archiveType"])
            # Make Java executable
            if not platform_id.value.startswith("win-"):
                os.chmod(java_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        assert os.path.exists(java_path), f"Java executable not found at {java_path}"

        # Setup BSL Language Server JAR
        bsl_dir = os.path.join(static_dir, "bsl-ls")
        os.makedirs(bsl_dir, exist_ok=True)

        # Step 1: Apply staged version if exists (from previous background download)
        staged_jar_path = cls._apply_staged_version(static_dir, bsl_dir)
        if staged_jar_path:
            bsl_jar_path = staged_jar_path
            current_version = cls._extract_version_from_jar_name(os.path.basename(bsl_jar_path))
        else:
            # Step 2: Check if JAR already exists
            existing_jars = [f for f in os.listdir(bsl_dir) if f.endswith("-exec.jar")] if os.path.exists(bsl_dir) else []

            if existing_jars:
                bsl_jar_path = os.path.join(bsl_dir, existing_jars[0])
                current_version = cls._extract_version_from_jar_name(existing_jars[0])
                log.info(f"Using existing BSL Language Server JAR: {bsl_jar_path}")

                # Update version info if not set
                version_info = cls._read_version_info(static_dir)
                if not version_info.current:
                    version_info.current = current_version
                    cls._write_version_info(static_dir, version_info)
            else:
                # Step 3: Download version (pinned or latest)
                download_url, version, is_pinned = cls._get_pinned_or_latest_version(solidlsp_settings, static_dir)

                if download_url:
                    jar_name = os.path.basename(download_url)
                    bsl_jar_path = os.path.join(bsl_dir, jar_name)

                    log.info(f"Downloading BSL Language Server {version}...")
                    FileUtils.download_and_extract_archive(download_url, bsl_jar_path, "binary")

                    # Update version info
                    version_info = cls._read_version_info(static_dir)
                    version_info.current = version
                    cls._write_version_info(static_dir, version_info)

                    current_version = version
                else:
                    # Offline and no existing JAR - this is an error
                    raise RuntimeError("Cannot download BSL Language Server: no network access and no cached version")

        assert os.path.exists(bsl_jar_path), f"BSL Language Server JAR not found at {bsl_jar_path}"

        # Step 4: Start background update check (if not pinned)
        version_info = cls._read_version_info(static_dir)
        if not version_info.pinned:
            cls._start_background_update_check(current_version, static_dir, bsl_dir)

        return BslRuntimeDependencyPaths(
            java_path=java_path,
            java_home_path=java_home_path,
            bsl_jar_path=bsl_jar_path,
        )

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the BSL Language Server.
        """
        if not os.path.isabs(repository_absolute_path):
            repository_absolute_path = os.path.abspath(repository_absolute_path)

        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "clientInfo": {"name": "Serena BSL Client", "version": "1.0.0"},
            "locale": "ru",
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "capabilities": {
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {
                        "documentChanges": True,
                        "resourceOperations": ["create", "rename", "delete"],
                        "failureHandling": "textOnlyTransactional",
                        "normalizesLineEndings": True,
                    },
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "didChangeWatchedFiles": {"dynamicRegistration": True, "relativePatternSupport": True},
                    "symbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "tagSupport": {"valueSet": [1]},
                    },
                    "codeLens": {"refreshSupport": True},
                    "executeCommand": {"dynamicRegistration": True},
                    "configuration": True,
                    "workspaceFolders": True,
                    "diagnostics": {"refreshSupport": True},
                },
                "textDocument": {
                    "publishDiagnostics": {
                        "relatedInformation": True,
                        "versionSupport": False,
                        "tagSupport": {"valueSet": [1, 2]},
                        "codeDescriptionSupport": True,
                        "dataSupport": True,
                    },
                    "synchronization": {"dynamicRegistration": True, "willSave": True, "willSaveWaitUntil": True, "didSave": True},
                    "completion": {
                        "dynamicRegistration": True,
                        "contextSupport": True,
                        "completionItem": {
                            "snippetSupport": False,
                            "commitCharactersSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "deprecatedSupport": True,
                            "preselectSupport": True,
                            "tagSupport": {"valueSet": [1]},
                            "insertReplaceSupport": False,
                            "resolveSupport": {"properties": ["documentation", "detail", "additionalTextEdits"]},
                            "insertTextModeSupport": {"valueSet": [1, 2]},
                            "labelDetailsSupport": True,
                        },
                        "insertTextMode": 2,
                        "completionItemKind": {
                            "valueSet": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
                        },
                    },
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {
                        "dynamicRegistration": True,
                        "signatureInformation": {
                            "documentationFormat": ["markdown", "plaintext"],
                            "parameterInformation": {"labelOffsetSupport": True},
                            "activeParameterSupport": True,
                        },
                        "contextSupport": True,
                    },
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "references": {"dynamicRegistration": True},
                    "documentHighlight": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "hierarchicalDocumentSymbolSupport": True,
                        "tagSupport": {"valueSet": [1]},
                        "labelSupport": True,
                    },
                    "codeAction": {
                        "dynamicRegistration": True,
                        "isPreferredSupport": True,
                        "disabledSupport": True,
                        "dataSupport": True,
                        "resolveSupport": {"properties": ["edit"]},
                        "codeActionLiteralSupport": {
                            "codeActionKind": {
                                "valueSet": [
                                    "",
                                    "quickfix",
                                    "refactor",
                                    "refactor.extract",
                                    "refactor.inline",
                                    "refactor.rewrite",
                                    "source",
                                    "source.organizeImports",
                                ]
                            }
                        },
                        "honorsChangeAnnotations": False,
                    },
                    "codeLens": {"dynamicRegistration": True},
                    "formatting": {"dynamicRegistration": True},
                    "rangeFormatting": {"dynamicRegistration": True},
                    "rename": {
                        "dynamicRegistration": True,
                        "prepareSupport": True,
                        "prepareSupportDefaultBehavior": 1,
                        "honorsChangeAnnotations": True,
                    },
                    "documentLink": {"dynamicRegistration": True, "tooltipSupport": True},
                    "foldingRange": {
                        "dynamicRegistration": True,
                        "rangeLimit": 5000,
                        "lineFoldingOnly": True,
                        "foldingRangeKind": {"valueSet": ["comment", "imports", "region"]},
                    },
                    "callHierarchy": {"dynamicRegistration": True},
                },
                "window": {
                    "showMessage": {"messageActionItem": {"additionalPropertiesSupport": True}},
                    "showDocument": {"support": True},
                    "workDoneProgress": True,
                },
                "general": {
                    "staleRequestSupport": {"cancel": True, "retryOnContentModified": []},
                    "regularExpressions": {"engine": "ECMAScript", "version": "ES2020"},
                    "positionEncodings": ["utf-16"],
                },
            },
            "initializationOptions": {
                "workspaceFolders": [root_uri],
            },
            "trace": "verbose",
            "processId": os.getpid(),
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
        }
        return cast(InitializeParams, initialize_params)

    def _start_server(self) -> None:
        """
        Starts the BSL Language Server
        """

        def do_nothing(params: dict) -> None:
            return

        def window_log_message(msg: dict) -> None:
            log.info(f"LSP: window/logMessage: {msg}")

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        log.info("Starting BSL Language Server process")
        self.server.start()
        initialize_params = self._get_initialize_params(self.repository_root_path)

        log.info("Sending initialize request from LSP client to LSP server and awaiting response")
        init_response = self.server.send.initialize(initialize_params)

        capabilities = init_response.get("capabilities", {})
        log.info(f"BSL Language Server capabilities: {list(capabilities.keys())}")

        # BSL LS provides these capabilities
        if "completionProvider" in capabilities:
            self.completions_available.set()

        if "diagnosticProvider" in capabilities:
            self.diagnostics_available.set()
            log.info("BSL Language Server diagnostics enabled")

        self.server.notify.initialized({})

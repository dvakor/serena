"""
Unit tests for BSL Language Server helper methods.

These tests validate the internal methods of BslLanguageServer without
requiring the full language server to be running. They test:
- Config file detection
- Memory setting extraction
- Version parsing from JAR filenames
- Staged version application

Tests are designed to run offline without network access.
"""

import json
import os
from typing import Any

import pytest

from solidlsp.language_servers.bsl_language_server import (
    BSL_CONFIG_FILENAME,
    DEFAULT_BSL_MEMORY,
    STAGED_DIR_NAME,
    VERSION_FILENAME,
    BslLanguageServer,
    VersionInfo,
)
from solidlsp.ls_config import Language
from solidlsp.settings import SolidLSPSettings


@pytest.mark.bsl
class TestFindConfigFile:
    """Test _find_config_file() - found and not found cases."""

    def test_find_config_file_exists(self, tmp_path: Any) -> None:
        """Test that config file is found when it exists."""
        # Create config file
        config_file = tmp_path / BSL_CONFIG_FILENAME
        config_file.write_text('{"diagnosticLanguage": "ru"}')

        result = BslLanguageServer._find_config_file(str(tmp_path))

        assert result is not None
        assert result == str(config_file)
        assert os.path.isfile(result)

    def test_find_config_file_not_exists(self, tmp_path: Any) -> None:
        """Test that None is returned when config file does not exist."""
        result = BslLanguageServer._find_config_file(str(tmp_path))

        assert result is None

    def test_find_config_file_empty_dir(self, tmp_path: Any) -> None:
        """Test that None is returned for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = BslLanguageServer._find_config_file(str(empty_dir))

        assert result is None

    def test_find_config_file_directory_not_file(self, tmp_path: Any) -> None:
        """Test that None is returned when .bsl-language-server.json is a directory, not a file."""
        # Create a directory with the config filename (edge case)
        config_dir = tmp_path / BSL_CONFIG_FILENAME
        config_dir.mkdir()

        result = BslLanguageServer._find_config_file(str(tmp_path))

        assert result is None


@pytest.mark.bsl
class TestGetMemorySetting:
    """Test _get_memory_setting() - default, explicit, and jvm_options extraction."""

    def test_memory_setting_default_when_no_settings(self) -> None:
        """Test that default memory is returned when no settings are provided."""
        settings = SolidLSPSettings(ls_specific_settings={})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == DEFAULT_BSL_MEMORY

    def test_memory_setting_default_when_no_bsl_settings(self) -> None:
        """Test that default memory is returned when BSL settings are empty."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == DEFAULT_BSL_MEMORY

    def test_memory_setting_explicit_memory(self) -> None:
        """Test that explicit memory setting takes priority."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"memory": "8G"}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == "8G"

    def test_memory_setting_explicit_memory_with_lowercase(self) -> None:
        """Test that memory setting works with lowercase (8g)."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"memory": "16g"}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == "16g"

    def test_memory_setting_from_jvm_options(self) -> None:
        """Test that memory is extracted from jvm_options when no explicit memory."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"jvm_options": "-Xmx12G -XX:+UseG1GC"}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == "12G"

    def test_memory_setting_explicit_overrides_jvm_options(self) -> None:
        """Test that explicit memory setting takes priority over jvm_options -Xmx."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"memory": "8G", "jvm_options": "-Xmx16G -XX:+UseG1GC"}})

        result = BslLanguageServer._get_memory_setting(settings)

        # Explicit memory should win over jvm_options
        assert result == "8G"

    def test_memory_setting_jvm_options_without_xmx(self) -> None:
        """Test that default is returned when jvm_options has no -Xmx flag."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"jvm_options": "-XX:+UseG1GC -XX:MaxGCPauseMillis=200"}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == DEFAULT_BSL_MEMORY

    def test_memory_setting_jvm_options_with_megabytes(self) -> None:
        """Test that memory is extracted from jvm_options with megabyte suffix."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"jvm_options": "-Xmx4096M"}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == "4096M"

    def test_memory_setting_jvm_options_numeric_only(self) -> None:
        """Test that memory is extracted when -Xmx has no suffix."""
        settings = SolidLSPSettings(ls_specific_settings={Language.BSL: {"jvm_options": "-Xmx2048"}})

        result = BslLanguageServer._get_memory_setting(settings)

        assert result == "2048"


@pytest.mark.bsl
class TestExtractVersionFromJarName:
    """Test _extract_version_from_jar_name() - version parsing from JAR filenames."""

    def test_extract_version_standard_format(self) -> None:
        """Test version extraction from standard JAR filename."""
        jar_name = "bsl-language-server-0.28.0-exec.jar"

        result = BslLanguageServer._extract_version_from_jar_name(jar_name)

        assert result == "v0.28.0"

    def test_extract_version_different_version(self) -> None:
        """Test version extraction with different version numbers."""
        test_cases = [
            ("bsl-language-server-1.0.0-exec.jar", "v1.0.0"),
            ("bsl-language-server-0.1.0-exec.jar", "v0.1.0"),
            ("bsl-language-server-10.20.30-exec.jar", "v10.20.30"),
            ("bsl-language-server-0.0.1-exec.jar", "v0.0.1"),
        ]

        for jar_name, expected_version in test_cases:
            result = BslLanguageServer._extract_version_from_jar_name(jar_name)
            assert result == expected_version, f"Failed for {jar_name}"

    def test_extract_version_invalid_format(self) -> None:
        """Test that None is returned for invalid JAR filename format."""
        invalid_names = [
            "bsl-language-server.jar",  # No version
            "some-other-jar-1.0.0.jar",  # Wrong prefix
            "bsl-language-server-0.28.0.jar",  # Missing -exec suffix
            "bsl-language-server-abc-exec.jar",  # Non-numeric version
            "",  # Empty string
            "random-file.txt",  # Not a JAR
        ]

        for name in invalid_names:
            result = BslLanguageServer._extract_version_from_jar_name(name)
            assert result is None, f"Expected None for '{name}', got '{result}'"

    def test_extract_version_partial_match(self) -> None:
        """Test that only complete version format is matched."""
        # This should not match because version format is incomplete
        jar_name = "bsl-language-server-0.28-exec.jar"

        result = BslLanguageServer._extract_version_from_jar_name(jar_name)

        assert result is None


@pytest.mark.bsl
class TestVersionInfo:
    """Test VersionInfo dataclass serialization."""

    def test_version_info_to_dict(self) -> None:
        """Test VersionInfo serialization to dictionary."""
        info = VersionInfo(current="v0.28.0", staged="v0.29.0", last_check="2024-01-15T12:00:00Z", pinned=None)

        result = info.to_dict()

        assert result == {
            "current": "v0.28.0",
            "staged": "v0.29.0",
            "last_check": "2024-01-15T12:00:00Z",
            "pinned": None,
        }

    def test_version_info_from_dict(self) -> None:
        """Test VersionInfo deserialization from dictionary."""
        data = {
            "current": "v0.28.0",
            "staged": None,
            "last_check": "2024-01-15T12:00:00Z",
            "pinned": "v0.27.0",
        }

        result = VersionInfo.from_dict(data)

        assert result.current == "v0.28.0"
        assert result.staged is None
        assert result.last_check == "2024-01-15T12:00:00Z"
        assert result.pinned == "v0.27.0"

    def test_version_info_from_dict_partial(self) -> None:
        """Test VersionInfo deserialization with missing fields."""
        data = {"current": "v0.28.0"}

        result = VersionInfo.from_dict(data)

        assert result.current == "v0.28.0"
        assert result.staged is None
        assert result.last_check is None
        assert result.pinned is None

    def test_version_info_default(self) -> None:
        """Test VersionInfo default values."""
        info = VersionInfo()

        assert info.current is None
        assert info.staged is None
        assert info.last_check is None
        assert info.pinned is None


@pytest.mark.bsl
class TestApplyStagedVersion:
    """Test _apply_staged_version() - success and failure cases."""

    def test_apply_staged_version_no_staged_dir(self, tmp_path: Any) -> None:
        """Test that None is returned when staged directory does not exist."""
        static_dir = str(tmp_path / "static")
        bsl_dir = str(tmp_path / "bsl-ls")
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(bsl_dir, exist_ok=True)

        result = BslLanguageServer._apply_staged_version(static_dir, bsl_dir)

        assert result is None

    def test_apply_staged_version_empty_staged_dir(self, tmp_path: Any) -> None:
        """Test that None is returned when staged directory is empty."""
        static_dir = str(tmp_path / "static")
        bsl_dir = str(tmp_path / "bsl-ls")
        staged_dir = os.path.join(bsl_dir, STAGED_DIR_NAME)
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(staged_dir, exist_ok=True)

        result = BslLanguageServer._apply_staged_version(static_dir, bsl_dir)

        assert result is None

    def test_apply_staged_version_success(self, tmp_path: Any) -> None:
        """Test successful staged version application."""
        static_dir = str(tmp_path / "static")
        bsl_dir = str(tmp_path / "bsl-ls")
        staged_dir = os.path.join(bsl_dir, STAGED_DIR_NAME)
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(staged_dir, exist_ok=True)

        # Create staged JAR
        staged_jar_name = "bsl-language-server-0.29.0-exec.jar"
        staged_jar_path = os.path.join(staged_dir, staged_jar_name)
        with open(staged_jar_path, "w") as f:
            f.write("staged jar content")

        # Create version info
        version_info = VersionInfo(current="v0.28.0", staged="v0.29.0")
        version_file = os.path.join(static_dir, VERSION_FILENAME)
        with open(version_file, "w") as f:
            json.dump(version_info.to_dict(), f)

        result = BslLanguageServer._apply_staged_version(static_dir, bsl_dir)

        # Verify result
        assert result is not None
        expected_path = os.path.join(bsl_dir, staged_jar_name)
        assert result == expected_path
        assert os.path.exists(expected_path)

        # Verify version info was updated
        with open(version_file) as f:
            updated_info = VersionInfo.from_dict(json.load(f))
        assert updated_info.current == "v0.29.0"
        assert updated_info.staged is None

        # Verify staged directory was cleaned up
        assert not os.path.exists(staged_dir)

    def test_apply_staged_version_removes_old_jar(self, tmp_path: Any) -> None:
        """Test that old JAR is removed when applying staged version."""
        static_dir = str(tmp_path / "static")
        bsl_dir = str(tmp_path / "bsl-ls")
        staged_dir = os.path.join(bsl_dir, STAGED_DIR_NAME)
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(staged_dir, exist_ok=True)

        # Create old JAR in main directory
        old_jar_name = "bsl-language-server-0.28.0-exec.jar"
        old_jar_path = os.path.join(bsl_dir, old_jar_name)
        with open(old_jar_path, "w") as f:
            f.write("old jar content")

        # Create staged JAR
        staged_jar_name = "bsl-language-server-0.29.0-exec.jar"
        staged_jar_path = os.path.join(staged_dir, staged_jar_name)
        with open(staged_jar_path, "w") as f:
            f.write("staged jar content")

        result = BslLanguageServer._apply_staged_version(static_dir, bsl_dir)

        # Verify old JAR was removed
        assert not os.path.exists(old_jar_path)

        # Verify new JAR was moved
        assert result is not None
        assert os.path.exists(result)
        with open(result) as f:
            assert f.read() == "staged jar content"

    def test_apply_staged_version_no_jars_in_staged(self, tmp_path: Any) -> None:
        """Test that None is returned when staged directory has no JAR files."""
        static_dir = str(tmp_path / "static")
        bsl_dir = str(tmp_path / "bsl-ls")
        staged_dir = os.path.join(bsl_dir, STAGED_DIR_NAME)
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(staged_dir, exist_ok=True)

        # Create non-JAR file in staged directory
        other_file = os.path.join(staged_dir, "readme.txt")
        with open(other_file, "w") as f:
            f.write("readme")

        result = BslLanguageServer._apply_staged_version(static_dir, bsl_dir)

        assert result is None


@pytest.mark.bsl
class TestReadWriteVersionInfo:
    """Test _read_version_info and _write_version_info methods."""

    def test_read_version_info_no_file(self, tmp_path: Any) -> None:
        """Test that default VersionInfo is returned when file does not exist."""
        static_dir = str(tmp_path)

        result = BslLanguageServer._read_version_info(static_dir)

        assert result.current is None
        assert result.staged is None
        assert result.last_check is None
        assert result.pinned is None

    def test_read_version_info_valid_file(self, tmp_path: Any) -> None:
        """Test reading valid version.json file."""
        static_dir = str(tmp_path)
        version_file = os.path.join(static_dir, VERSION_FILENAME)

        data = {"current": "v0.28.0", "staged": "v0.29.0", "last_check": "2024-01-15T12:00:00Z", "pinned": None}
        with open(version_file, "w") as f:
            json.dump(data, f)

        result = BslLanguageServer._read_version_info(static_dir)

        assert result.current == "v0.28.0"
        assert result.staged == "v0.29.0"
        assert result.last_check == "2024-01-15T12:00:00Z"
        assert result.pinned is None

    def test_read_version_info_invalid_json(self, tmp_path: Any) -> None:
        """Test that default VersionInfo is returned for invalid JSON."""
        static_dir = str(tmp_path)
        version_file = os.path.join(static_dir, VERSION_FILENAME)

        with open(version_file, "w") as f:
            f.write("not valid json {{{")

        result = BslLanguageServer._read_version_info(static_dir)

        # Should return default VersionInfo on error
        assert result.current is None

    def test_write_version_info(self, tmp_path: Any) -> None:
        """Test writing version.json file."""
        static_dir = str(tmp_path)
        version_file = os.path.join(static_dir, VERSION_FILENAME)

        version_info = VersionInfo(current="v0.28.0", staged=None, last_check="2024-01-15T12:00:00Z", pinned="v0.28.0")

        BslLanguageServer._write_version_info(static_dir, version_info)

        assert os.path.exists(version_file)
        with open(version_file) as f:
            data = json.load(f)

        assert data["current"] == "v0.28.0"
        assert data["staged"] is None
        assert data["last_check"] == "2024-01-15T12:00:00Z"
        assert data["pinned"] == "v0.28.0"

    def test_write_and_read_roundtrip(self, tmp_path: Any) -> None:
        """Test that write followed by read returns the same data."""
        static_dir = str(tmp_path)

        original = VersionInfo(current="v1.0.0", staged="v1.1.0", last_check="2024-06-15T08:30:00Z", pinned=None)

        BslLanguageServer._write_version_info(static_dir, original)
        result = BslLanguageServer._read_version_info(static_dir)

        assert result.current == original.current
        assert result.staged == original.staged
        assert result.last_check == original.last_check
        assert result.pinned == original.pinned


@pytest.mark.bsl
class TestShouldCheckForUpdates:
    """Test _should_check_for_updates method."""

    def test_should_check_when_pinned(self) -> None:
        """Test that update check is skipped when version is pinned."""
        version_info = VersionInfo(current="v0.28.0", pinned="v0.28.0")

        result = BslLanguageServer._should_check_for_updates(version_info)

        assert result is False

    def test_should_check_when_no_last_check(self) -> None:
        """Test that update check is performed when last_check is None."""
        version_info = VersionInfo(current="v0.28.0", last_check=None)

        result = BslLanguageServer._should_check_for_updates(version_info)

        assert result is True

    def test_should_check_when_enough_time_passed(self) -> None:
        """Test that update check is performed when enough time has passed."""
        from datetime import UTC, datetime, timedelta

        from solidlsp.language_servers.bsl_language_server import UPDATE_CHECK_INTERVAL_SECONDS

        # Set last check to be old enough
        old_time = datetime.now(UTC) - timedelta(seconds=UPDATE_CHECK_INTERVAL_SECONDS + 100)
        version_info = VersionInfo(current="v0.28.0", last_check=old_time.isoformat())

        result = BslLanguageServer._should_check_for_updates(version_info)

        assert result is True

    def test_should_not_check_when_recently_checked(self) -> None:
        """Test that update check is skipped when recently checked."""
        from datetime import UTC, datetime

        # Set last check to now
        version_info = VersionInfo(current="v0.28.0", last_check=datetime.now(UTC).isoformat())

        result = BslLanguageServer._should_check_for_updates(version_info)

        assert result is False

    def test_should_check_when_invalid_timestamp(self) -> None:
        """Test that update check is performed when timestamp is invalid."""
        version_info = VersionInfo(current="v0.28.0", last_check="invalid-timestamp")

        result = BslLanguageServer._should_check_for_updates(version_info)

        assert result is True


@pytest.mark.bsl
class TestParseGitHubReleaseResponse:
    """Test version parsing from GitHub releases API response."""

    def test_parse_latest_release_finds_exec_jar(self) -> None:
        """Test that the parsing logic correctly identifies -exec.jar assets."""
        # This tests the logic pattern used in _get_latest_bsl_release_url
        # We test the asset filtering logic without making network calls
        assets = [
            {"name": "bsl-language-server-0.28.0.zip", "browser_download_url": "https://example.com/zip"},
            {"name": "bsl-language-server-0.28.0-exec.jar", "browser_download_url": "https://example.com/exec.jar"},
            {"name": "checksum.txt", "browser_download_url": "https://example.com/checksum"},
        ]

        # Find the exec JAR (same logic as in _get_latest_bsl_release_url)
        exec_jar = None
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith("-exec.jar"):
                exec_jar = asset
                break

        assert exec_jar is not None
        assert exec_jar["name"] == "bsl-language-server-0.28.0-exec.jar"
        assert exec_jar["browser_download_url"] == "https://example.com/exec.jar"

    def test_parse_release_no_exec_jar(self) -> None:
        """Test handling when -exec.jar asset is missing."""
        assets = [
            {"name": "bsl-language-server-0.28.0.zip", "browser_download_url": "https://example.com/zip"},
            {"name": "checksum.txt", "browser_download_url": "https://example.com/checksum"},
        ]

        exec_jar = None
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith("-exec.jar"):
                exec_jar = asset
                break

        assert exec_jar is None

    def test_parse_release_empty_assets(self) -> None:
        """Test handling when assets list is empty."""
        assets: list[dict[str, str]] = []

        exec_jar = None
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith("-exec.jar"):
                exec_jar = asset
                break

        assert exec_jar is None

    def test_parse_release_version_matching(self) -> None:
        """Test version matching logic for pinned versions."""
        # This tests the logic in _get_release_url_for_version
        releases = [
            {"tag_name": "v0.28.0", "assets": [{"name": "bsl-language-server-0.28.0-exec.jar", "browser_download_url": "url1"}]},
            {"tag_name": "v0.27.0", "assets": [{"name": "bsl-language-server-0.27.0-exec.jar", "browser_download_url": "url2"}]},
            {"tag_name": "v0.26.0", "assets": [{"name": "bsl-language-server-0.26.0-exec.jar", "browser_download_url": "url3"}]},
        ]

        # Test finding v0.27.0 (same logic as in _get_release_url_for_version)
        target_version = "0.27.0"
        normalized_version = f"v{target_version}" if not target_version.startswith("v") else target_version

        found_release = None
        for release in releases:
            tag = release.get("tag_name", "")
            if tag in (normalized_version, target_version):
                found_release = release
                break

        assert found_release is not None
        assert found_release["tag_name"] == "v0.27.0"

    def test_parse_release_version_with_v_prefix(self) -> None:
        """Test version matching works with v prefix in both formats."""
        releases = [
            {"tag_name": "v0.28.0", "assets": [{"name": "bsl-language-server-0.28.0-exec.jar", "browser_download_url": "url"}]},
        ]

        # Both "v0.28.0" and "0.28.0" should match
        for target in ["v0.28.0", "0.28.0"]:
            normalized = f"v{target}" if not target.startswith("v") else target

            found = None
            for release in releases:
                tag = release.get("tag_name", "")
                if tag in (normalized, target):
                    found = release
                    break

            assert found is not None, f"Failed to match {target}"

    def test_parse_release_version_not_found(self) -> None:
        """Test handling when requested version is not in releases list."""
        releases = [
            {"tag_name": "v0.28.0", "assets": []},
            {"tag_name": "v0.27.0", "assets": []},
        ]

        target_version = "v0.25.0"
        normalized_version = f"v{target_version}" if not target_version.startswith("v") else target_version

        found_release = None
        for release in releases:
            tag = release.get("tag_name", "")
            if tag in (normalized_version, target_version):
                found_release = release
                break

        assert found_release is None

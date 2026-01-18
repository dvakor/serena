## ADDED Requirements

### Requirement: Configurable JVM Memory

The BSL Language Server SHALL support configurable JVM heap size via `ls_specific_settings.bsl.memory` setting.

The default memory SHALL be `4G` to match VS Code behavior on large projects.

#### Scenario: Memory from explicit setting

- **WHEN** `ls_specific_settings.bsl.memory` is set to `"8G"`
- **THEN** the JVM is started with `-Xmx8G` flag

#### Scenario: Memory from jvm_options (backward compatibility)

- **WHEN** `ls_specific_settings.bsl.jvm_options` contains `-Xmx6G`
- **AND** `ls_specific_settings.bsl.memory` is not set
- **THEN** the JVM is started with `-Xmx6G` flag

#### Scenario: Default memory

- **WHEN** neither `memory` nor `-Xmx` in `jvm_options` is specified
- **THEN** the JVM is started with `-Xmx4G` flag

---

### Requirement: Automatic Configuration File Detection

The BSL Language Server SHALL automatically detect and apply project configuration from `.bsl-language-server.json` file.

#### Scenario: Configuration file exists

- **WHEN** `.bsl-language-server.json` exists in the project root
- **THEN** the `-c <path>` flag is passed to the BSL Language Server

#### Scenario: Configuration file does not exist

- **WHEN** `.bsl-language-server.json` does not exist in the project root
- **THEN** no `-c` flag is passed
- **AND** BSL Language Server uses its default configuration

---

### Requirement: Automatic Version Updates

The BSL Language Server SHALL automatically check for and download new versions from GitHub releases.

Updates SHALL be applied silently at the next startup (staged update pattern).

#### Scenario: New version available

- **WHEN** BSL Language Server starts
- **AND** a newer version is available on GitHub
- **THEN** the new version is downloaded in background
- **AND** the update is applied at next startup
- **AND** INFO log message indicates available update

#### Scenario: Offline operation

- **WHEN** BSL Language Server starts
- **AND** GitHub is not accessible
- **THEN** the currently installed version is used
- **AND** WARNING log message indicates update check failed

#### Scenario: Staged version exists

- **WHEN** BSL Language Server starts
- **AND** a staged (previously downloaded) version exists
- **THEN** the staged version becomes the active version
- **AND** INFO log message indicates version was updated

---

### Requirement: Version Pinning

The BSL Language Server SHALL support pinning to a specific version via `ls_specific_settings.bsl.version` setting.

When a version is pinned, automatic updates SHALL be disabled for that installation.

#### Scenario: Pinned version

- **WHEN** `ls_specific_settings.bsl.version` is set to `"0.28.0"`
- **THEN** version `0.28.0` is downloaded and used
- **AND** automatic update checks are skipped

#### Scenario: Pinned version not available

- **WHEN** `ls_specific_settings.bsl.version` is set to a non-existent version
- **THEN** the latest available version is used
- **AND** WARNING log message indicates pinned version not found

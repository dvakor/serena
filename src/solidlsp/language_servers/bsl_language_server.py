"""
Provides BSL (1C:Enterprise) specific instantiation of the LanguageServer class.
Contains various configurations and settings specific to BSL/OneScript.

BSL Language Server provides support for:
- 1C:Enterprise 8 source files (*.bsl)
- OneScript files (*.os)

You can configure the following options in ls_specific_settings (in serena_config.yml):

    ls_specific_settings:
      bsl:
        jvm_options: '-Xmx2G'  # JVM options for BSL Language Server (default: -Xmx2G)

Example configuration:

    ls_specific_settings:
      bsl:
        jvm_options: '-Xmx4G'

Note: Language for diagnostics can be configured via .bsl-language-server.json file in project root.
"""

import dataclasses
import json
import logging
import os
import pathlib
import stat
import urllib.request
from typing import cast

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)

# Default JVM options for BSL Language Server
DEFAULT_BSL_JVM_OPTIONS = "-Xmx2G"

# GitHub API URL for latest release
BSL_LS_GITHUB_API_URL = "https://api.github.com/repos/1c-syntax/bsl-language-server/releases/latest"


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

        # Get JVM options from settings or use default
        jvm_options = DEFAULT_BSL_JVM_OPTIONS

        if solidlsp_settings.ls_specific_settings:
            bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
            custom_jvm_options = bsl_settings.get("jvm_options", "")
            if custom_jvm_options:
                jvm_options = custom_jvm_options
                log.info(f"Using custom JVM options for BSL Language Server: {jvm_options}")

        # Build command to run BSL Language Server
        # Note: BSL LS in LSP mode doesn't accept --language flag, it's only for analyzer mode
        # Language configuration is done via .bsl-language-server.json config file
        cmd = [
            self.runtime_dependency_paths.java_path,
            *jvm_options.split(),
            "-jar",
            self.runtime_dependency_paths.bsl_jar_path,
        ]

        # Set environment variables including JAVA_HOME
        proc_env = {
            "JAVA_HOME": self.runtime_dependency_paths.java_home_path,
        }

        super().__init__(
            config, repository_root_path, ProcessLaunchInfo(cmd=cmd, env=proc_env, cwd=repository_root_path), "bsl", solidlsp_settings
        )

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

        # Check if JAR already exists
        existing_jars = [f for f in os.listdir(bsl_dir) if f.endswith("-exec.jar")] if os.path.exists(bsl_dir) else []

        if existing_jars:
            bsl_jar_path = os.path.join(bsl_dir, existing_jars[0])
            log.info(f"Using existing BSL Language Server JAR: {bsl_jar_path}")
        else:
            # Download latest release
            download_url, version = cls._get_latest_bsl_release_url()
            jar_name = os.path.basename(download_url)
            bsl_jar_path = os.path.join(bsl_dir, jar_name)

            log.info(f"Downloading BSL Language Server {version}...")
            FileUtils.download_and_extract_archive(download_url, bsl_jar_path, "binary")

        assert os.path.exists(bsl_jar_path), f"BSL Language Server JAR not found at {bsl_jar_path}"

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

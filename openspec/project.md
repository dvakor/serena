# Project Context

## Purpose
Serena is a coding agent toolkit that provides IDE-like semantic code retrieval and editing tools to LLMs. It enables AI coding agents to work directly on codebases using symbol-level operations (like `find_symbol`, `find_referencing_symbols`, `insert_after_symbol`) instead of basic file reads and grep-like searches. The project is LLM-agnostic and framework-agnostic, integrating via the Model Context Protocol (MCP).

**Key Value Proposition**: Unlike grep-like searches and basic file reads, Serena understands code structure at the symbol level, allowing agents to efficiently navigate and modify large codebases.

## Tech Stack
- **Language**: Python 3.11 (strict version requirement: >=3.11, <3.12)
- **Package Management**: uv with hatchling build backend
- **Task Runner**: poethepoet (`poe`)
- **Core Protocols**: MCP (Model Context Protocol), LSP (Language Server Protocol)
- **Version**: 0.1.4
- **Packages** (in wheel): `serena`, `solidlsp`, `interprompt`
- **Key Dependencies**:
  - `mcp==1.23.0` - Model Context Protocol SDK
  - `pydantic>=2.10.6` - Data validation and settings
  - `flask>=3.0.0` - Web framework components (dashboard)
  - `pyright>=1.1.396` - Python language server
  - `anthropic>=0.54.0` - Anthropic SDK for AI integration
  - `tiktoken>=0.9.0` - Token counting
  - `psutil>=7.0.0` - Process management for language servers
- **Optional Dependencies**:
  - `agno` - Agno framework integration
  - `google` - Google Generative AI integration

## Project Conventions

### Code Style
- **Formatter**: Black (line-length: 140)
- **Linter**: Ruff (comprehensive rule set with specific ignores)
- **Type Checking**: mypy with strict settings (`disallow_untyped_defs`, `strict_optional`, etc.)
- **Commands**:
  - `uv run poe format` - Format code (ONLY allowed formatting command)
  - `uv run poe type-check` - Run mypy (ONLY allowed type checking command)
  - `uv run poe lint` - Check style without fixing
- **Always run format, type-check, and test before completing any task**

### Architecture Patterns
- **Dual-layer architecture**: SerenaAgent orchestrates, SolidLanguageServer handles LSP
- **Tool-based design**: All functionality exposed as discrete tools inheriting from `Tool` base class
- **Configuration hierarchy**: CLI args > project `.serena/project.yml` > user config > active modes/contexts
- **Core Packages**:
  - `serena` - Main agent, tools, configuration, MCP server
  - `solidlsp` - LSP abstraction layer, language server implementations
  - `interprompt` - Prompt templating utilities
- **Core Components**:
  - `SerenaAgent` (`src/serena/agent.py`) - Central orchestrator
  - `SolidLanguageServer` (`src/solidlsp/ls.py`) - LSP wrapper
  - Tool System (`src/serena/tools/`):
    - `file_tools.py` - File system operations, search, regex replacements
    - `symbol_tools.py` - Language-aware symbol finding, navigation, editing
    - `memory_tools.py` - Project knowledge persistence and retrieval
    - `config_tools.py` - Project activation, mode switching
    - `workflow_tools.py` - Onboarding and meta-operations
    - `jetbrains_tools.py` - JetBrains IDE integration
  - Configuration System (`src/serena/config/`):
    - `serena_config.py` - Main configuration management
    - `context_mode.py` - Contexts (tool sets) and modes (operational patterns)
  - Language Servers (`src/solidlsp/language_servers/`) - 42 language server implementations

### Testing Strategy
- **Framework**: pytest with language-specific markers, syrupy for snapshots
- **Run tests**: `uv run poe test` (excludes java/rust by default)
- **Selective testing**: `uv run poe test -m "python or go"` for specific languages
- **All Markers**: al, bash, bsl, clojure, csharp, dart, elixir, elm, erlang, fortran, fsharp, go, groovy, haskell, java, julia, kotlin, lua, markdown, matlab, nix, pascal, perl, php, powershell, python, r, rego, ruby, ruby_solargraph, rust, scala, slow, snapshot, swift, terraform, toml, typescript, vue, yaml, zig
- **Snapshot tests**: For symbolic editing operations (`-m snapshot`)
- **Test resources**: Test repositories in `test/resources/repos/<language>/`
- **Test suites**: Language-specific tests in `test/solidlsp/<language>/`
- **Parallel execution**: pytest-xdist available (`-n auto`)
- **Timeout**: pytest-timeout for long-running tests

### Git Workflow
- Main branch: `main`
- Standard feature branch workflow
- Commit message convention: Clear, descriptive messages

## Domain Context
- **LSP (Language Server Protocol)**: Standard protocol for IDE-like features (go-to-definition, find references, completions)
- **MCP (Model Context Protocol)**: Anthropic's protocol for exposing tools to AI agents
- **Symbol-based editing**: Precise code manipulation at the symbol level rather than line-based editing
- **Language servers**: External processes implementing LSP for specific languages
- **Memory system**: Markdown-based project knowledge persistence in `.serena/memories/`

### Supported Languages (42 total)
**Production Languages** (auto-detected):
AL, Bash, BSL (1C:Enterprise/OneScript), C#, C/C++, Clojure, Dart, Elixir, Elm, Erlang, F#, Fortran, Go, Haskell, Java, Julia, Kotlin, Lua, MATLAB, Nix, Pascal, Perl, PHP, PowerShell, Python, R, Rego, Ruby, Rust, Scala, Swift, Terraform, TypeScript, Vue, Zig

**Experimental Languages** (must be explicitly configured):
Groovy, Markdown, YAML, TOML, TypeScript (VTS variant), Python (Jedi variant), C# (OmniSharp variant), Ruby (Solargraph variant)

## Important Constraints
- Python version strictly 3.11.x (not 3.10, not 3.12+)
- Language servers run as separate processes with their own dependencies
- Some language servers require additional system dependencies
- MCP server must be started from project root for proper path resolution

## External Dependencies
- **Language Servers**: Various LSP implementations:
  - Python: pyright (default), jedi (alternative)
  - TypeScript/JavaScript: typescript-language-server, vtsls (alternative)
  - Go: gopls
  - Rust: rust-analyzer
  - Java: Eclipse JDT.LS
  - C#: csharp-ls (default), OmniSharp (alternative)
  - Ruby: ruby-lsp (default), Solargraph (alternative)
  - BSL: bsl-language-server (requires Java 17+)
  - Vue: @vue/language-server
  - And 30+ more...
- **MCP SDK**: `mcp==1.23.0` for protocol implementation
- **Runtime Downloads**: Some language servers are downloaded automatically when needed
- **JetBrains Plugin**: Optional alternative backend using JetBrains IDE capabilities
- **GitHub Repository**: https://github.com/oraios/serena

## CLI Entry Points
- `serena` - Main CLI interface
- `serena-mcp-server` - Start MCP server (must be run from project root)
- `index-project` - Index project for faster tool performance (deprecated)

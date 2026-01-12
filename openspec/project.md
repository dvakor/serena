# Project Context

## Purpose
Serena is a coding agent toolkit that provides IDE-like semantic code retrieval and editing tools to LLMs. It enables AI coding agents to work directly on codebases using symbol-level operations (like `find_symbol`, `find_referencing_symbols`, `insert_after_symbol`) instead of basic file reads and grep-like searches. The project is LLM-agnostic and framework-agnostic, integrating via the Model Context Protocol (MCP).

## Tech Stack
- **Language**: Python 3.11 (strict version requirement: >=3.11, <3.12)
- **Package Management**: uv with hatchling build backend
- **Task Runner**: poethepoet (`poe`)
- **Core Protocols**: MCP (Model Context Protocol), LSP (Language Server Protocol)
- **Key Dependencies**:
  - `mcp` - Model Context Protocol SDK
  - `pydantic` - Data validation and settings
  - `flask` - Web framework components
  - `pyright` - Python language server
  - `anthropic` - Anthropic SDK for AI integration

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
- **Core Components**:
  - `SerenaAgent` (`src/serena/agent.py`) - Central orchestrator
  - `SolidLanguageServer` (`src/solidlsp/ls.py`) - LSP wrapper
  - Tool System (`src/serena/tools/`) - file_tools, symbol_tools, memory_tools, config_tools, workflow_tools
  - Configuration System (`src/serena/config/`) - contexts, modes, projects

### Testing Strategy
- **Framework**: pytest with language-specific markers
- **Run tests**: `uv run poe test` (excludes java/rust by default)
- **Selective testing**: `uv run poe test -m "python or go"` for specific languages
- **Markers**: python, go, java, rust, typescript, vue, php, perl, powershell, csharp, elixir, terraform, clojure, swift, bash, ruby, bsl, and many more
- **Snapshot tests**: For symbolic editing operations (`-m snapshot`)
- **Test resources**: Test repositories in `test/resources/repos/<language>/`
- **Test suites**: Language-specific tests in `test/solidlsp/<language>/`

### Git Workflow
- Main branch: `main`
- Standard feature branch workflow
- Commit message convention: Clear, descriptive messages

## Domain Context
- **LSP (Language Server Protocol)**: Standard protocol for IDE-like features (go-to-definition, find references, completions)
- **MCP (Model Context Protocol)**: Anthropic's protocol for exposing tools to AI agents
- **Symbol-based editing**: Precise code manipulation at the symbol level rather than line-based editing
- **Language servers**: External processes implementing LSP for specific languages
- **30+ supported languages**: Including Python, TypeScript, Go, Java, Rust, C#, Ruby, PHP, and many others
- **Memory system**: Markdown-based project knowledge persistence in `.serena/memories/`

## Important Constraints
- Python version strictly 3.11.x (not 3.10, not 3.12+)
- Language servers run as separate processes with their own dependencies
- Some language servers require additional system dependencies
- MCP server must be started from project root for proper path resolution

## External Dependencies
- **Language Servers**: Various LSP implementations (pyright, gopls, rust-analyzer, etc.)
- **MCP SDK**: `mcp==1.23.0` for protocol implementation
- **Runtime Downloads**: Some language servers are downloaded automatically when needed
- **JetBrains Plugin**: Optional alternative backend using JetBrains IDE capabilities
- **GitHub Repository**: https://github.com/oraios/serena

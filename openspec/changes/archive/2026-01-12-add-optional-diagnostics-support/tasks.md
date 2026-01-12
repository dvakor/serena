## 1. SolidLSP Layer - Base

- [x] 1.1 Add `diagnostics_available` threading.Event to `SolidLanguageServer` base class (`src/solidlsp/ls.py`)
- [x] 1.2 Add capability check in `request_text_document_diagnostics()` to raise clear error if diagnostics not available

## 2. SolidLSP Layer - Language Server Implementations

- [x] 2.1 Enable diagnostics in `BslLanguageServer._start_server()` by setting `diagnostics_available` after checking server capabilities (`src/solidlsp/language_servers/bsl_language_server.py`)
- [x] 2.2 Enable diagnostics in `TypeScriptLanguageServer._start_server()` by setting `diagnostics_available` (`src/solidlsp/language_servers/typescript_language_server.py`)
- [x] 2.3 Enable diagnostics in `CSharpLanguageServer._start_server()` by setting `diagnostics_available` - leverage existing `_force_pull_diagnostics` (`src/solidlsp/language_servers/csharp_language_server.py`)

## 3. Serena Tool Layer

- [x] 3.1 Create `GetDiagnosticsTool` class in `src/serena/tools/symbol_tools.py`
- [x] 3.2 Tool should check `diagnostics_available` before attempting to retrieve diagnostics
- [x] 3.3 Return user-friendly message when diagnostics not supported for current language server

## 4. Testing

- [x] 4.1 Add test for diagnostics retrieval in `test/solidlsp/bsl/`
- [x] 4.2 Add test for diagnostics retrieval in `test/solidlsp/typescript/`
- [x] 4.3 Add test for diagnostics retrieval in `test/solidlsp/csharp/`
- [x] 4.4 Add test verifying graceful handling when diagnostics unavailable

## 5. Validation

- [x] 5.1 Run `uv run poe format`
- [x] 5.2 Run `uv run poe type-check`
- [x] 5.3 Run `uv run poe test -m bsl`
- [x] 5.4 Run `uv run poe test -m typescript`
- [x] 5.5 Run `uv run poe test -m csharp`

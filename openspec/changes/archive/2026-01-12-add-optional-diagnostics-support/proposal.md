# Change: Add Optional Diagnostics Support

## Why
Language servers can provide code diagnostics (errors, warnings, hints) but not all servers support this capability. Currently, `SolidLanguageServer.request_text_document_diagnostics()` exists but:
1. It's not exposed as a Serena tool
2. There's no capability detection to gracefully handle servers that don't support diagnostics
3. Language server implementations cannot opt-in/opt-out of exposing diagnostics

## What Changes
- Add capability detection for diagnostics support in `SolidLanguageServer`
- Allow concrete language server implementations to explicitly expose diagnostics
- Add a new `get_diagnostics` Serena tool that retrieves diagnostics for a file
- Tool availability depends on both LSP capability AND explicit LS implementation opt-in
- Enable diagnostics for: **TypeScript**, **BSL**, **C#**

## Impact
- Affected specs: `diagnostics` (new capability)
- Affected code:
  - `src/solidlsp/ls.py` - Add diagnostics capability flag and detection
  - `src/solidlsp/language_servers/bsl_language_server.py` - Enable diagnostics exposure
  - `src/solidlsp/language_servers/typescript_language_server.py` - Enable diagnostics exposure
  - `src/solidlsp/language_servers/csharp_language_server.py` - Enable diagnostics exposure (already has `_force_pull_diagnostics`)
  - `src/serena/tools/symbol_tools.py` - Add `get_diagnostics` tool

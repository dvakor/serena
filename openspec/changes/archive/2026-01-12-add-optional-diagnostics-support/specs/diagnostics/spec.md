## ADDED Requirements

### Requirement: Diagnostics Capability Detection
The system SHALL detect whether a language server supports diagnostics by checking for `diagnosticProvider` in the server's reported capabilities during initialization.

#### Scenario: Server supports diagnostics
- **WHEN** a language server reports `diagnosticProvider` capability during initialization
- **THEN** the system recognizes that the server can provide diagnostics

#### Scenario: Server does not support diagnostics
- **WHEN** a language server does not report `diagnosticProvider` capability
- **THEN** the system recognizes that diagnostics are unavailable for this server

### Requirement: Explicit Diagnostics Opt-in
Concrete language server implementations SHALL explicitly opt-in to expose diagnostics by setting the `diagnostics_available` flag, even if the LSP server reports the capability.

#### Scenario: Language server opts in to diagnostics
- **WHEN** a concrete LS implementation sets `diagnostics_available` after verifying server capability
- **THEN** diagnostics become available for that language server

#### Scenario: Language server does not opt in
- **WHEN** a concrete LS implementation does not set `diagnostics_available`
- **THEN** diagnostics remain unavailable even if the underlying LSP server supports them

### Requirement: Supported Language Servers
The following language servers SHALL have diagnostics enabled: TypeScript, BSL, and C#.

#### Scenario: TypeScript diagnostics enabled
- **WHEN** using TypeScriptLanguageServer
- **THEN** diagnostics are available and can be retrieved

#### Scenario: BSL diagnostics enabled
- **WHEN** using BslLanguageServer
- **THEN** diagnostics are available and can be retrieved

#### Scenario: C# diagnostics enabled
- **WHEN** using CSharpLanguageServer
- **THEN** diagnostics are available and can be retrieved

### Requirement: Get Diagnostics Tool
The system SHALL provide a `get_diagnostics` tool that retrieves code diagnostics (errors, warnings, hints) for a specified file.

#### Scenario: Retrieve diagnostics for file with issues
- **WHEN** user requests diagnostics for a file containing code issues
- **AND** the language server has diagnostics enabled
- **THEN** the tool returns a list of diagnostics with severity, message, and location

#### Scenario: Retrieve diagnostics for clean file
- **WHEN** user requests diagnostics for a file with no issues
- **AND** the language server has diagnostics enabled
- **THEN** the tool returns an empty list

#### Scenario: Diagnostics unavailable for language server
- **WHEN** user requests diagnostics
- **AND** the current language server does not have diagnostics enabled
- **THEN** the tool returns a user-friendly message indicating diagnostics are not available for this language server

## Context

Diagnostics are a core LSP feature that provide code analysis feedback (errors, warnings, hints). The LSP specification defines two approaches:
1. **Push model**: Server sends `textDocument/publishDiagnostics` notifications
2. **Pull model**: Client requests via `textDocument/diagnostic`

Currently, `SolidLanguageServer` has `request_text_document_diagnostics()` using the pull model, but it's not exposed to Serena and lacks capability detection.

## Goals / Non-Goals

**Goals:**
- Enable diagnostics retrieval for language servers that support it
- Make diagnostics opt-in at the language server implementation level
- Expose diagnostics as a Serena tool when available
- Gracefully handle servers that don't support diagnostics

**Non-Goals:**
- Implementing the push model (notifications)
- Auto-enabling diagnostics for all language servers
- Caching or aggregating diagnostics across files

## Decisions

### Decision 1: Two-level opt-in mechanism
Diagnostics require BOTH:
1. LSP server capability (`diagnosticProvider` in server capabilities)
2. Explicit opt-in in the concrete LS implementation (setting `diagnostics_available` flag)

**Rationale**: Some servers report capability but have unreliable implementations. Explicit opt-in ensures only tested/working implementations expose diagnostics.

### Decision 2: Use existing pull model
Continue using `textDocument/diagnostic` request (pull model) rather than collecting from `publishDiagnostics` notifications.

**Rationale**: Pull model is simpler, on-demand, and already implemented. Push model would require notification accumulation and state management.

### Decision 3: Add `diagnostics_available` threading.Event
Follow the existing pattern used for `completions_available` - a threading.Event that concrete LS implementations set when they support and want to expose diagnostics.

**Alternatives considered:**
- Boolean flag: Less flexible, can't wait for async initialization
- Configuration option: Would require config changes; capability should be intrinsic to LS

## Risks / Trade-offs

- **Risk**: Some language servers may have diagnostics capability but poor implementation
  - **Mitigation**: Explicit opt-in means only tested servers expose diagnostics

- **Trade-off**: Pull model means diagnostics are fetched on-demand, not continuously updated
  - **Acceptable**: Matches Serena's request-response tool pattern

## Open Questions

None - implementation approach is clear.

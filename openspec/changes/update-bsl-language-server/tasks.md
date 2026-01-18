## 1. Core Configuration Changes

- [x] 1.1 Add `DEFAULT_BSL_MEMORY = "4G"` constant
- [x] 1.2 Implement `_get_memory_setting()` method to extract memory from settings
- [x] 1.3 Implement `_find_config_file()` method to locate `.bsl-language-server.json`
- [x] 1.4 Update command building to use new memory setting
- [x] 1.5 Add `-c` flag with config path to command when config exists

## 2. Auto-Update Mechanism

- [x] 2.1 Create `version.json` schema and read/write helpers
- [x] 2.2 Implement `_apply_staged_version()` to activate downloaded updates
- [x] 2.3 Implement `_get_pinned_or_latest_version()` to determine target version
- [x] 2.4 Implement `_start_background_update_check()` daemon thread
- [x] 2.5 Implement `_check_and_download_update()` with GitHub API call
- [x] 2.6 Add file locking for staged directory operations

## 3. Update `_setup_runtime_dependencies`

- [x] 3.1 Refactor to support version pinning
- [x] 3.2 Add staged version application at startup
- [x] 3.3 Start background update check after LS initialization
- [x] 3.4 Handle graceful degradation when offline

## 4. Testing

- [x] 4.1 Unit test `_find_config_file()` - found and not found cases
- [x] 4.2 Unit test `_get_memory_setting()` - default, explicit, from jvm_options
- [x] 4.3 Unit test version parsing from GitHub releases API response
- [x] 4.4 Unit test `_apply_staged_version()` - success and failure cases
- [x] 4.5 Integration test BSL LS startup with new configuration (skipped - requires network)

## 5. Documentation

- [x] 5.1 Update CLAUDE.md with new BSL LS configuration options
- [x] 5.2 Add example configuration to bsl_language_server.py docstring

## Dependencies

- Task 1.x must complete before Task 3.x
- Task 2.x can be done in parallel with Task 1.x
- Task 4.x depends on corresponding implementation tasks
- Task 5.x can be done after Tasks 1-3 are complete

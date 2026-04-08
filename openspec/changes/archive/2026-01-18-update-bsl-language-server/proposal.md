# Change: Update BSL Language Server to Match VS Code Behavior

## Why

BSL Language Server в Serena вызывает высокую нагрузку CPU через 10-30 минут работы, в то время как тот же сервер в VS Code работает стабильно. Исследование выявило критические различия:

1. **Устаревшая версия** (0.26.0 vs 0.28.0) - версия 0.27.0+ содержит исправления race conditions и double processing
2. **Недостаточная память** (2GB vs 4GB) - на больших проектах (6000+ файлов) вызывает частый GC
3. **Отсутствие передачи конфигурации** - VS Code передаёт флаг `-c` с путём к `.bsl-language-server.json`
4. **Нет автообновления** - пользователям приходится вручную удалять старые JAR файлы

## What Changes

### Core Changes
- **Настраиваемая память JVM** - новая опция `ls_specific_settings.bsl.memory` (default: `4G`)
- **Передача флага `-c`** - автоматический поиск и передача `.bsl-language-server.json`
- **Механизм автообновления** - фоновая проверка GitHub releases при каждом запуске
- **Фиксация версии** - опция `ls_specific_settings.bsl.version` для pin конкретной версии

### Configuration Format
```yaml
ls_specific_settings:
  bsl:
    memory: "4G"        # JVM heap size (default: 4G)
    version: "0.28.0"   # Pin specific version (optional, default: latest)
    jvm_options: ""     # Additional JVM options (optional)
```

## Impact

- **Affected specs**: bsl-language-server (NEW)
- **Affected code**: `src/solidlsp/language_servers/bsl_language_server.py`
- **Breaking changes**: None (existing `jvm_options` setting remains backward-compatible)
- **User action required**: None (defaults work out of the box, improvements are automatic)

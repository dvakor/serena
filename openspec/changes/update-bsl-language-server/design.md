## Context

BSL Language Server - Java-приложение для поддержки языка 1C:Enterprise. При использовании через Serena наблюдается высокая нагрузка CPU, отсутствующая при работе через VS Code. Исследование показало различия в конфигурации запуска.

**Stakeholders**: Пользователи, работающие с 1С кодовыми базами через Serena.

**Constraints**:
- Обратная совместимость с существующими конфигурациями
- Минимальное влияние на время запуска
- Работа без интернета (graceful degradation)

## Goals / Non-Goals

**Goals**:
- Устранить CPU pressure при длительной работе BSL LS
- Автоматически обновлять BSL LS до актуальной версии
- Предоставить гибкую настройку памяти JVM
- Автоматически применять проектную конфигурацию BSL LS

**Non-Goals**:
- Изменение поведения других language servers
- Поддержка native image версии (как в VS Code) - требует отдельного исследования
- Интерактивные диалоги при обновлении

## Decisions

### Decision 1: Структура директорий для автообновления

```
~/.serena/language_servers/static/BslLanguageServer/
├── bsl-ls/
│   ├── bsl-language-server-0.28.0-exec.jar  # активная версия
│   └── .staged/
│       └── bsl-language-server-0.29.0-exec.jar  # скачанная новая
├── java/
│   └── ...
└── version.json  # метаданные
```

**Rationale**: Staged директория позволяет скачать новую версию без прерывания работы текущей. Применение происходит при следующем запуске.

### Decision 2: Фоновое обновление в отдельном потоке

```python
def _start_background_update_check(cls, current_version: str, bsl_dir: str):
    """Запустить фоновую проверку обновлений"""
    thread = threading.Thread(
        target=cls._check_and_download_update,
        args=(current_version, bsl_dir),
        daemon=True,
        name="BSL-LS-UpdateChecker"
    )
    thread.start()
```

**Rationale**: Daemon-поток не блокирует основную работу и автоматически завершается при остановке приложения.

### Decision 3: Формат version.json

```json
{
  "current": "0.28.0",
  "staged": "0.29.0",
  "last_check": "2025-01-18T12:00:00Z",
  "pinned": null
}
```

**Rationale**: Хранение метаданных позволяет отслеживать состояние обновлений и избежать повторных скачиваний.

### Decision 4: Приоритет настроек памяти

1. `ls_specific_settings.bsl.memory` (если указано)
2. Извлечение из `ls_specific_settings.bsl.jvm_options` (если содержит -Xmx)
3. Default: `4G`

**Rationale**: Обратная совместимость с существующими конфигурациями, использующими `jvm_options`.

## Alternatives Considered

### Alternative A: Мгновенное обновление с перезапуском LS

**Rejected because**: Прерывает работу пользователя, может вызвать потерю контекста в агенте.

### Alternative B: Использование native image как VS Code

**Deferred because**: Требует дополнительной инфраструктуры для скачивания platform-specific бинарников. Может быть добавлено позже.

### Alternative C: Проверка обновлений по расписанию

**Rejected because**: Усложняет логику, не даёт значительных преимуществ. При запуске - оптимальный момент.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| GitHub API rate limit | Кэширование результата в version.json, проверка не чаще 1 раза в час |
| Сбой скачивания | Retry с exponential backoff, продолжение работы со старой версией |
| Corrupted JAR | Проверка размера файла после скачивания, переименование из .tmp |
| Конфликт при параллельном запуске | File locking для операций с staged директорией |
| Отсутствие интернета | Graceful degradation - использовать локальную версию |

## Migration Plan

1. **Обновление по умолчанию**: При первом запуске после обновления Serena автоматически скачается актуальная версия BSL LS
2. **Существующие JAR**: Останутся работоспособными до появления новой версии
3. **Rollback**: Пользователь может указать `version: "0.26.0"` для возврата к старой версии

## Open Questions

- [ ] Нужно ли уведомлять пользователя о доступном обновлении через logging?
  - **Предлагаемый ответ**: Да, INFO-уровень логирования

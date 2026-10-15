## Context

У пользователя есть рабочие исправления OpenRGB/Kingston, Lian Li wireless, восстановления после suspend. Их нужно упаковать в переносимую интеграцию, а не привязать плагин к домашнему каталогу одного пользователя. Авторизован новый самостоятельный открытый проект с OpenSpec и параллельной реализацией.

## Goals / Non-Goals

Цель: установка плагина из GitHub, настройка поддерживаемого оборудования из панели, стабильное управление цветом и эффектами с восстановлением после сна. Первая версия поддерживает устройства, доступные OpenRGB, и известные Lian Li VID/PID. Список реально проверенного оборудования публикуется отдельно. Прошивки и SPD EEPROM не меняются; встроенное сохранение RGB в flash при движении ползунков не вызывается. LCD-медиа и произвольные новые протоколы не входят в первую версию.

## Decisions

1. Нативная QML-панель в существующем процессе Omarchy. UI обменивается JSON через CLI `bin/zorya-rgb`, без shell-конкатенации пользовательского текста.
2. Python-пакет `zorya_rgb/` хранит и валидирует состояние; daemon один на пользователя, Unix socket с правами0600. OpenRGB SDK только loopback. CLI возвращает JSON для UI.
3. Состояние: `on`, `color` (#RRGGBB), `brightness` (0..100), `effect` (static|pulse|rainbow|gradient), `speed` (0.1..5), `secondary_color`, `devices` (IDs), `presets` (имя+снимок настроек). Default color #FFFFFF. Stable device identity includes name+location+serial with deterministic fallback; duplicate names are not silently merged.
4. CLI contract: `status`, `devices`, `set --json OBJECT`, `preset save NAME`, `preset apply ID`, `preset delete ID`, `doctor`, `setup [--component openrgb|lianli|kingston|all]`, `install`, `uninstall`, `daemon`, `restore`, `migrate`, `pair --device ID`. `status` returns state fields plus `connected`, `error`, `setup`, `device_count`. `devices` returns JSON `{devices:[{id,name,selected,modes,led_count,location}],error:null}`. `set` validates atomically and applies through daemon; unknown keys fail with a clear JSON error.
5. Аппаратный режим выбирается по capabilities. Static использует аппаратный режим без повторной записи конфигурации во flash; состояние хранится в пользовательском JSON; анимация использует безопасный темп обновлений: по умолчанию до10FPS, Lian Li по возможности аппаратная буферизация. Не писать полный режим/яркость при каждом кадре. Одна ошибка устройства не блокирует остальные.
6. После BOOTTIME/MONOTONIC-разрыва daemon выполняет coordinated recovery: backend-specific restart/discovery/readiness, затем применяет сохранённый пресет. Установщик обеспечивает сериализацию с существующими сервисами; нет постоянных периодических resets.
7. Установка dependencies выполняется отдельным действием с отчетом/полкитом; install plugin != install all hardware tools. Разрешён adoption уже работающей локальной Lian Li/OpenRGB интеграции, но новый ПК получает переносимый pinned build/install path, udev и user units. Любое управление скоростью вентилятора требует отдельной настройки; default RGB adapter не меняет насос/LCD/кривые.
8. Новая панель оригинальная. Зависимости и заимствованные официальные patches имеют атрибуцию/лицензии. License GPL-3.0-or-later, поскольку openrgb-python лицензирован GPLv3; MIT-лицензия Lian Li и GPLv2-or-later OpenRGB сохраняются отдельно для соответствующих patches.

## Alternatives

- Расширить старую панель: быстрее, но оставляет распределённое состояние/скрипты и зависимость от чужого lifecycle.
- Полностью заменить OpenRGB собственными драйверами: чрезмерно широкая область поддержки.
- Выбран отдельный плагин с backend adapters: сохраняет существующую поддержку оборудования и делает восстановление/эффекты воспроизводимыми.

## Migration / Verification

Импортировать состояние старого RGB без удаления исходных файлов. Установка нового плагина сначала проверяется отдельно; переключение панели включает резервную копию shell.json. Тесты: валидация, эффекты, mocked SDK/capabilities, socket/security, sleep recovery, installer dry-run/fixtures. Omarchy manifest validation, qmllint и тест реального shell открытия/закрытия. Полный физический suspend и чистая установка всех hardware combinations отмечаются непроверенными, если не выполнены.

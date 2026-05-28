# Clinic Printer Switcher

Утилита для безопасной смены принтера по умолчанию в клинике.

## Возможности

- показывает текущий принтер по умолчанию;
- подтягивает актуальные принтеры из Windows;
- позволяет врачу выбрать принтер и сделать его основным;
- скрывает сложные системные имена принтеров;
- админ-режим через кнопку с шестерёнкой;
- в админ-режиме можно добавлять/переименовывать принтеры;
- может показывать врачам только добавленные принтеры;
- отключает автоматическое управление принтером Windows;
- пытается обновлять выбранный принтер в профилях Yandex Browser, Chrome и Edge.

## Установка зависимостей

```powershell
pip install -r requirements.txt
```

## Запуск

```powershell
python main.py
```

## PIN администратора

По умолчанию:

```text
2468
```

Конфиг хранится здесь:

```text
C:\ProgramData\ClinicPrinterSwitcher\printers.json
```

## Сборка в exe

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --name ClinicPrinterSwitcher main.py
```

Готовый exe будет здесь:

```text
dist\ClinicPrinterSwitcher.exe
```

## Важный нюанс про браузеры

Chrome / Yandex Browser / Edge могут перезаписывать настройки печати, если браузер открыт.

Лучше:
1. закрыть браузер;
2. сменить принтер в Clinic Printer Switcher;
3. открыть браузер заново.

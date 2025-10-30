# Установка шрифтов DejaVu для PDF на Windows

## Проблема

При генерации PDF файлов (списки покупок, рационы питания) вместо русских букв отображаются квадратики ☐☐☐.

Это происходит потому, что для корректного отображения кириллицы нужны шрифты DejaVu, которые не установлены на Windows по умолчанию.

## Решение

### Способ 1: Автоматическая установка (рекомендуется)

Создайте файл `install_fonts.bat` в папке проекта:

```batch
@echo off
echo Installing DejaVu fonts for PDF generation...

REM Создаем временную папку
mkdir temp_fonts 2>nul
cd temp_fonts

REM Скачиваем шрифты DejaVu
echo Downloading DejaVu fonts...
curl -L -o dejavu-fonts.zip "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"

REM Распаковываем
echo Extracting fonts...
tar -xf dejavu-fonts.zip

REM Копируем шрифты в системную папку
echo Installing fonts...
copy "dejavu-fonts-ttf-2.37\ttf\DejaVuSans.ttf" "%SystemRoot%\Fonts\"
copy "dejavu-fonts-ttf-2.37\ttf\DejaVuSans-Bold.ttf" "%SystemRoot%\Fonts\"

REM Регистрируем шрифты в реестре
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "DejaVu Sans (TrueType)" /t REG_SZ /d DejaVuSans.ttf /f
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "DejaVu Sans Bold (TrueType)" /t REG_SZ /d "DejaVuSans-Bold.ttf" /f

REM Очистка
cd ..
rmdir /s /q temp_fonts

echo.
echo ===================================
echo Fonts installed successfully!
echo ===================================
echo Please restart the bot:
echo python -m app.bot.main
echo.
pause
```

Запустите скрипт **от имени Администратора**.

### Способ 2: Ручная установка

1. **Скачайте шрифты DejaVu:**
   - Перейдите на https://dejavu-fonts.github.io/Download.html
   - Скачайте "DejaVu fonts" (version 2.37 или новее)
   - Или прямая ссылка: https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip

2. **Установите шрифты:**
   - Распакуйте архив
   - Откройте папку `ttf`
   - Найдите файлы:
     - `DejaVuSans.ttf`
     - `DejaVuSans-Bold.ttf`
   - Щелкните правой кнопкой мыши по каждому файлу → **"Установить"** или **"Install for all users"**

3. **Перезапустите бота:**
   ```cmd
   python -m app.bot.main
   ```

### Способ 3: Добавить шрифты в проект (без установки в систему)

1. Создайте папку `fonts` в корне проекта:
   ```cmd
   mkdir fonts
   ```

2. Скачайте и скопируйте файлы шрифтов в папку `fonts/`:
   - `fonts/DejaVuSans.ttf`
   - `fonts/DejaVuSans-Bold.ttf`

3. Перезапустите бота

## Проверка

После установки шрифтов:

1. Перезапустите бота
2. Создайте рацион питания или список покупок
3. В логах должно появиться:
   ```
   Registered DejaVuSans font from C:\Windows\Fonts\DejaVuSans.ttf
   Registered DejaVuSans-Bold font from C:\Windows\Fonts\DejaVuSans-Bold.ttf
   ```

4. Русский текст в PDF должен отображаться корректно ✅

## Устранение проблем

### Если в логах видите:
```
DejaVu fonts not found. Cyrillic text may not display correctly.
Please install DejaVu fonts
```

Это значит, что шрифты не найдены. Проверьте:

1. Шрифты установлены в `C:\Windows\Fonts\`
2. Имена файлов точно: `DejaVuSans.ttf` и `DejaVuSans-Bold.ttf`
3. Бот перезапущен после установки шрифтов

### Если используется Helvetica:
```
DejaVu fonts not available, using Helvetica
```

Шрифт Helvetica не поддерживает кириллицу, поэтому будут квадратики. Установите DejaVu шрифты.

## Дополнительно

Шрифты DejaVu - это бесплатные открытые шрифты с отличной поддержкой Unicode, включая кириллицу, греческий, арабский и другие алфавиты.

Лицензия: Free (Public Domain)
Сайт: https://dejavu-fonts.github.io/

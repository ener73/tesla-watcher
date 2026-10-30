# Richtet eine Windows-Aufgabe ein, die alle 10 Minuten unsichtbar im Hintergrund prüft
$TaskName = "TeslaInventoryWatcher"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command python).Source
$PythonwExe = Join-Path (Split-Path $PythonExe) "pythonw.exe"
if (-not (Test-Path $PythonwExe)) { $PythonwExe = $PythonExe }

$Action = New-ScheduledTaskAction -Execute $PythonwExe -Argument "`"$ScriptDir\tesla_watcher.py`" --once" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force
Write-Host "✅ Windows-Hintergrundaufgabe '$TaskName' erfolgreich eingerichtet (läuft alle 10 Minuten)." -ForegroundColor Green

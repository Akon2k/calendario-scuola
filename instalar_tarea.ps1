# Crea (o elimina) las tareas programadas: la del scraper y la de avisos.
# Se usa desde instalar_tarea.bat; se puede invocar a mano:
#   powershell -ExecutionPolicy Bypass -File instalar_tarea.ps1 -Hora 19:30
#   powershell -ExecutionPolicy Bypass -File instalar_tarea.ps1 -Eliminar
param(
    [string]$Hora = "07:00",
    [switch]$Eliminar
)

$nombre = "CalendarioEvaScuola"
$nombreAvisos = "CalendarioEvaScuolaAvisos"
$carpeta = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat = Join-Path $carpeta "tarea.bat"
$batAvisos = Join-Path $carpeta "avisos_dia.bat"

if ($Eliminar) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $nombreAvisos -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tareas '$nombre' y '$nombreAvisos' eliminadas."
    exit 0
}

if (-not (Test-Path $bat)) {
    Write-Error "No existe $bat"
    exit 1
}

# WorkingDirectory es importante: si no, el scraper correria en C:\Windows\System32.
$accion = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $carpeta
$disparo = New-ScheduledTaskTrigger -Daily -At $Hora
Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparo -Force | Out-Null

Write-Host "Tarea '$nombre' creada."
Write-Host "  Se ejecuta cada dia a las $Hora"
Write-Host "  Programa : $bat"
Write-Host "  Salida   : (salida)\calendario_evaluaciones.xlsx"
Write-Host "  Registro : logs\tarea.log"

# Segunda tarea: avisos cada hora de 08:00 a 22:00, para que una correccion
# hecha a media tarde se anuncie el mismo dia (el resumen del sabado se
# envia una sola vez: avisos.py se acuerda en logs\avisos_estado.json).
if (Test-Path $batAvisos) {
    $accion2 = New-ScheduledTaskAction -Execute $batAvisos -WorkingDirectory $carpeta
    $disparo2 = New-ScheduledTaskTrigger -Daily -At "08:00"
    # Repeticion diaria: se toma el patron de un disparo «una vez».
    # Hasta las 22:59 -> la última repetición es a las 22:00 (nada de madrugada).
    $patron = (New-ScheduledTaskTrigger -Once -At "08:00" `
        -RepetitionInterval (New-TimeSpan -Minutes 60) `
        -RepetitionDuration (New-TimeSpan -Minutes 899)).Repetition
    $disparo2.Repetition = $patron
    Register-ScheduledTask -TaskName $nombreAvisos -Action $accion2 -Trigger $disparo2 -Force | Out-Null
    Write-Host ""
    Write-Host "Tarea '$nombreAvisos' creada."
    Write-Host "  Se ejecuta cada hora de 08:00 a 22:00 (avisos del mismo dia)"
    Write-Host "  Programa : $batAvisos"
    Write-Host "  Registro : logs\avisos_dia.log"
}

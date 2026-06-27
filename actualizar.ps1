# Actualizacion nocturna: baja resultados nuevos + cuotas y re-genera predicciones.
$ErrorActionPreference = "Continue"
$proj = "C:\Users\carlo\Pictures\Desarollos para usuarios\Emilio\Predictivo"
$py = Join-Path $proj ".venv\Scripts\python.exe"
$log = Join-Path $proj "actualizacion.log"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Set-Location $proj

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $log "`n========== [$ts] Inicio =========="

# 1) Resultados nuevos del repositorio de datos
try { git -C "$proj\data_repo" pull 2>&1 | Add-Content $log } catch { Add-Content $log "git pull fallo: $_" }

# 2) Datos externos (cuotas 1X2 + campeón + clima; el resto usa caché)
try { & $py "$proj\fetch_all.py" 2>&1 | Add-Content $log } catch { Add-Content $log "fetch_all fallo: $_" }

# 3) Re-generar predicciones (lee solo de data_user/, cero API extra)
try { & $py "$proj\build.py" 2>&1 | Add-Content $log } catch { Add-Content $log "build fallo: $_" }

$ts2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $log "[$ts2] Fin."

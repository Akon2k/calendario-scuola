# Genera los iconos de la PWA una sola vez en edufacil\web\
# (son assets del proyecto: no hace falta volver a correrlo).
#   powershell -File generar_iconos.ps1
Add-Type -AssemblyName System.Drawing

$destino = Join-Path $PSScriptRoot "edufacil\web"
New-Item -ItemType Directory -Force -Path $destino | Out-Null

$azul    = [System.Drawing.Color]::FromArgb(255, 37, 99, 235)    # #2563eb
$azulOsc = [System.Drawing.Color]::FromArgb(255, 29, 78, 216)    # #1d4ed8
$hoja    = [System.Drawing.Color]::FromArgb(255, 248, 250, 255)
$gris    = [System.Drawing.Color]::FromArgb(255, 156, 163, 175)  # #9ca3af
$rojo    = [System.Drawing.Color]::FromArgb(255, 239, 68, 68)    # #ef4444

function Rect-Redondo([System.Drawing.Graphics]$g, [double]$x, [double]$y,
                      [double]$w, [double]$h, [double]$r, [System.Drawing.Brush]$b) {
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = [single]($r * 2)
  if ($d -lt 2) {
    $p.AddRectangle([System.Drawing.RectangleF]::new([single]$x, [single]$y,
                                                     [single]$w, [single]$h))
  } else {
    $p.AddArc([single]$x, [single]$y, $d, $d, 180, 90)
    $p.AddArc([single]($x + $w - 2 * $r), [single]$y, $d, $d, 270, 90)
    $p.AddArc([single]($x + $w - 2 * $r), [single]($y + $h - 2 * $r), $d, $d, 0, 90)
    $p.AddArc([single]$x, [single]($y + $h - 2 * $r), $d, $d, 90, 90)
    $p.CloseFigure()
  }
  $g.FillPath($b, $p)
  $p.Dispose()
}

# modos: redondeado (any), maskable (fondo a sangre + zona segura), sangre (iOS)
function Nueva-Icono([int]$tam, [string]$modo, [string]$ruta) {
  $bmp = New-Object System.Drawing.Bitmap($tam, $tam)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.Clear([System.Drawing.Color]::Transparent)

  if ($modo -eq 'redondeado') {
    $bAzul = New-Object System.Drawing.SolidBrush $azul
    Rect-Redondo $g 0 0 $tam $tam ($tam * 0.20) $bAzul
    $bAzul.Dispose()
    $u = $tam / 1000.0
    $ox = 0.0
    $oy = 0.0
  } else {
    $g.Clear($azul)
    $margen = if ($modo -eq 'maskable') { 0.10 } else { 0.05 }
    $u = ($tam * (1 - 2 * $margen)) / 1000.0
    $ox = $tam * $margen
    $oy = $tam * $margen
  }

  $g.TranslateTransform([single]$ox, [single]$oy)
  $g.ScaleTransform([single]$u, [single]$u)   # de aquí en adelante: lienzo 0..1000

  $bHoja = New-Object System.Drawing.SolidBrush $hoja
  Rect-Redondo $g 160 260 680 580 90 $bHoja   # la hoja del calendario
  $bHoja.Dispose()

  $bBlanco = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
  $bAzulOsc = New-Object System.Drawing.SolidBrush $azulOsc
  foreach ($x in 320, 620) {                  # anillas: blancas sobre el fondo…
    Rect-Redondo $g $x 165 60 200 30 $bBlanco
    Rect-Redondo $g $x 265 60 100 30 $bAzulOsc   # …azules sobre la hoja
  }
  $bBlanco.Dispose()
  $bAzulOsc.Dispose()

  # puntos de los días; el rojo marca la evaluación de hoy
  $puntos = @(@(300, 470, $gris), @(500, 470, $rojo), @(700, 470, $gris),
              @(300, 650, $gris), @(500, 650, $gris), @(700, 650, $gris))
  foreach ($p in $puntos) {
    $b = New-Object System.Drawing.SolidBrush $p[2]
    $cx = [double]$p[0]
    $cy = [double]$p[1]
    $g.FillEllipse($b, [single]($cx - 55), [single]($cy - 55), [single]110, [single]110)
    $b.Dispose()
  }

  $g.ResetTransform()
  $g.Dispose()
  $bmp.Save($ruta, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
}

Nueva-Icono 192 'redondeado' (Join-Path $destino "icon-192.png")
Nueva-Icono 512 'redondeado' (Join-Path $destino "icon-512.png")
Nueva-Icono 512 'maskable'   (Join-Path $destino "icon-maskable-512.png")
Nueva-Icono 180 'sangre'     (Join-Path $destino "apple-touch-icon.png")

Get-ChildItem $destino -Filter *.png | Select-Object Name, Length

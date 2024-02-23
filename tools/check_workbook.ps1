# Opens the report pack in Excel, sets the rates, types a test forecast, recalculates, and writes every formula result
# to JSON for gr.check_workbook.
#   powershell -File tools/check_workbook.ps1 -Path excel/GCC-Market-Report.xlsx -Out xl.json [-Sar 3.75] [-Bhd 0.376]
# The test forecast: on Forecast input row r (r = 3, 4, ...), units in quarter q are 1000 * (r - 2) + 100 * q, and
# rows where (r mod 3) = 0 have a generic entering in quarter 2. Python applies the same rule.
param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Out, [double]$Sar = 3.75, [double]$Bhd = 0.376)
$ErrorActionPreference = "Stop"
trap { Write-Host ("FAILED at line " + $_.InvocationInfo.ScriptLineNumber + ": " + $_.InvocationInfo.Line.Trim()); break }
$full = (Resolve-Path $Path).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false

function Read-Block($ws, $firstRow, $keyCol, $cols) {
  $out = @()
  $r = $firstRow
  while ($ws.Cells.Item($r, $keyCol).Value2) {
    $row = @()
    foreach ($c in $cols) { $row += , $ws.Cells.Item($r, $c).Value2 }
    $out += , $row
    $r++
  }
  return , $out
}

try {
  $wb = $xl.Workbooks.Open($full, 0, $true)
  $inp = $wb.Worksheets.Item("Inputs")
  $inp.Range("B1").Value2 = $Sar
  $inp.Range("B2").Value2 = $Bhd
  $fi = $wb.Worksheets.Item("Forecast input")
  $r = 3
  while ($fi.Cells.Item($r, 1).Value2) {
    $cols = @("E", "F", "G", "H")
    for ($q = 1; $q -le 4; $q++) { $fi.Range($cols[$q - 1] + [string]$r).Value2 = [double](1000 * ($r - 2) + 100 * $q) }
    if ($r % 3 -eq 0) { $fi.Range("I" + [string]$r).Value2 = [double]2 }
    $r++
  }
  $xl.CalculateFull()
  $res = @{
    sar = $Sar; bhd = $Bhd
    products = (Read-Block $wb.Worksheets.Item("Products") 2 1 @(12, 13))
    competition = (Read-Block $wb.Worksheets.Item("Competition") 2 1 @(1, 2, 3, 4, 5, 6, 7, 8))
    gcc = (Read-Block $wb.Worksheets.Item("GCC prices") 2 1 @(1, 5, 7, 8))
    reference = (Read-Block $wb.Worksheets.Item("Reference pricing") 2 1 @(1, 5, 6, 8, 9))
    forecast = (Read-Block $fi 3 1 @(4, 10, 11, 12, 13, 14))
    summary = (Read-Block $wb.Worksheets.Item("Forecast summary") 2 1 @(1, 2, 7))
  }
  $wb.Close($false)
  ($res | ConvertTo-Json -Depth 6 -Compress) | Out-File -FilePath $Out -Encoding utf8
  "ok"
} finally {
  $xl.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}

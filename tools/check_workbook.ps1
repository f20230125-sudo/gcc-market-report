# Opens the report pack in Excel, recalculates it, and writes the formula results to JSON for gr.check_workbook.
#   powershell -File tools/check_workbook.ps1 -Path excel/GCC-Market-Report.xlsx -Out excel-results.json [-Rate 3.75]
param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Out, [double]$Rate = 3.75)
$ErrorActionPreference = "Stop"
$full = (Resolve-Path $Path).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($full, 0, $true)
  $wb.Worksheets.Item("Inputs").Range("B1").Value2 = $Rate
  $xl.CalculateFull()
  $res = @{ rate = $Rate; generic = @(); reference = @(); products = @() }
  $g = $wb.Worksheets.Item("Generic pressure")
  $r = 2
  while ($g.Cells.Item($r, 1).Value2) {
    $res.generic += ,@($g.Cells.Item($r, 1).Value2, $g.Cells.Item($r, 3).Value2, $g.Cells.Item($r, 4).Value2, $g.Cells.Item($r, 5).Value2, $g.Cells.Item($r, 6).Value2, $g.Cells.Item($r, 7).Value2)
    $r++
  }
  $s = $wb.Worksheets.Item("Reference pricing")
  $r = 2
  while ($s.Cells.Item($r, 1).Value2) {
    $res.reference += ,@($s.Cells.Item($r, 1).Value2, $s.Cells.Item($r, 5).Value2, $s.Cells.Item($r, 6).Value2)
    $r++
  }
  $p = $wb.Worksheets.Item("Products")
  $r = 2
  while ($p.Cells.Item($r, 4).Value2) {
    $res.products += ,@($p.Cells.Item($r, 15).Text, $p.Cells.Item($r, 10).Value2, $p.Cells.Item($r, 11).Value2)
    $r++
  }
  $wb.Close($false)
  ($res | ConvertTo-Json -Depth 5 -Compress) | Out-File -FilePath $Out -Encoding utf8
  "ok"
} finally {
  $xl.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}

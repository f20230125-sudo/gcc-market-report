# Opens the project in Power BI Desktop, refreshes its model through the engine Desktop runs, evaluates every measure
# with DAX, and writes the results to JSON for gr.check_powerbi. Optionally captures each page (the Power BI window only).
#   powershell -File tools/check_powerbi_engine.ps1 -Pbip powerbi/GCCMarketReport.pbip -Out pbi.json [-Shots <folder outside the repo>]
# Uses the Tabular object model and ADOMD client that ship with Power BI Desktop (Microsoft.PowerBI.Tabular.dll and
# Microsoft.PowerBI.AdomdClient.dll), the way external tools connect to Desktop. The Desktop process it started is
# closed at the end without saving.
param([Parameter(Mandatory = $true)][string]$Pbip, [Parameter(Mandatory = $true)][string]$Out, [string]$Shots = "")
$ErrorActionPreference = "Stop"
$bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
Add-Type -Path (Join-Path $bin "Microsoft.PowerBI.Tabular.dll")
Add-Type -Path (Join-Path $bin "Microsoft.PowerBI.AdomdClient.dll")
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W2 {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
$UIA = [System.Windows.Automation.AutomationElement]
$SCOPE = [System.Windows.Automation.TreeScope]

$started = Get-Date
$proc = Start-Process -FilePath (Join-Path $bin "PBIDesktop.exe") -ArgumentList ('"' + (Resolve-Path $Pbip).Path + '"') -PassThru
try {
  # The engine writes its port to a workspace folder created for this session.
  $ws = Join-Path $env:LOCALAPPDATA "Microsoft\Power BI Desktop\AnalysisServicesWorkspaces"
  $port = $null
  for ($i = 0; $i -lt 120 -and -not $port; $i++) {
    Start-Sleep -Seconds 2
    $f = Get-ChildItem $ws -Recurse -Filter "msmdsrv.port.txt" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $started } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) { $port = ([System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::Unicode)).Trim() }
  }
  if (-not $port) { throw "no engine port found" }
  "engine port: $port"
  Start-Sleep -Seconds 30  # let Desktop finish loading the model

  $server = New-Object Microsoft.AnalysisServices.Tabular.Server
  $server.Connect("localhost:$port")
  $db = $server.Databases[0]
  "model: " + $db.Model.Tables.Count + " tables, " + (($db.Model.Tables | ForEach-Object { $_.Measures.Count }) | Measure-Object -Sum).Sum + " measures, " + $db.Model.Relationships.Count + " relationships"
  $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
  $t0 = Get-Date
  [void]$db.Model.SaveChanges()
  "refreshed in " + [int]((Get-Date) - $t0).TotalSeconds + " s"
  $rows = @{}
  foreach ($t in $db.Model.Tables) {
    $p = $t.Partitions[0]
    $rows[$t.Name] = @{ state = $p.State.ToString(); error = $p.ErrorMessage }
  }

  $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
  $conn.Open()
  function Q($dax) {
    $cmd = $conn.CreateCommand(); $cmd.CommandText = $dax
    $r = $cmd.ExecuteReader(); $out = @()
    while ($r.Read()) { $row = @(); for ($i = 0; $i -lt $r.FieldCount; $i++) { $row += , ($(if ($r.IsDBNull($i)) { $null } else { $r.GetValue($i) })) }; $out += , $row }
    $r.Close(); return , $out
  }
  $res = @{
    partitions = $rows
    counts = (Q "EVALUATE ROW(""p"", COUNTROWS(fact_products), ""c"", COUNTROWS(fact_competition), ""g"", COUNTROWS(fact_gcc_prices), ""r"", COUNTROWS(fact_reference), ""b"", COUNTROWS(fact_bahrain_changes), ""v"", COUNTROWS(fact_validation))")
    by_country = (Q "EVALUATE SUMMARIZECOLUMNS(dim_country[country], ""Products"", [Products], ""MSD"", [MSD Products], ""Generic"", [Generic Versions], ""Other"", [Other Brands], ""Companies"", [Companies], ""Median"", [Median Price per Unit USD], ""Checks"", [Checks], ""Failed"", [Checks Failed])")
    by_ingredient = (Q "EVALUATE SUMMARIZECOLUMNS(fact_products[country], fact_products[ingredient], ""MSDLow"", [MSD Lowest per Unit USD], ""GenLow"", [Cheapest Generic per Unit USD], ""Disc"", [Cheapest Generic vs MSD])")
    gcc = (Q "EVALUATE ROW(""n"", [Products Compared], ""med"", [Median Saudi vs Bahrain], ""cheaper"", [Saudi Cheaper], ""us"", [US over GCC (median)], ""matched"", [Prices Matched], ""same"", [Share Unchanged], ""medchg"", [Median Change], ""genpm"", [Generic Versions per Molecule])")
  }
  $conn.Close()
  $server.Disconnect()

  if ($Shots) {
    $c = New-Object System.Windows.Automation.PropertyCondition($UIA::ProcessIdProperty, $proc.Id)
    $w = $UIA::RootElement.FindAll($SCOPE::Children, $c) | Where-Object { $_.Current.Name -like "*GCCMarketReport*" } | Select-Object -First 1
    foreach ($pg in @("Overview", "Competition", "Saudi vs Bahrain", "US reference", "Bahrain 2024 to 2026", "Data quality")) {
      $tab = $w.FindFirst($SCOPE::Descendants, (New-Object System.Windows.Automation.PropertyCondition($UIA::NameProperty, $pg)))
      if (-not $tab) { continue }
      $sp = $null
      if ($tab.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$sp)) { $sp.Select() } elseif ($tab.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$sp)) { $sp.Invoke() }
      Start-Sleep -Seconds 8
      $h = [IntPtr]$w.Current.NativeWindowHandle; $rc = New-Object W2+RECT; [void][W2]::GetWindowRect($h, [ref]$rc)
      $bmp = New-Object System.Drawing.Bitmap ($rc.R - $rc.L), ($rc.B - $rc.T); $g = [System.Drawing.Graphics]::FromImage($bmp)
      $dc = $g.GetHdc(); [void][W2]::PrintWindow($h, $dc, 2); $g.ReleaseHdc($dc)
      $bmp.Save((Join-Path $Shots ("pbi-" + ($pg -replace '[^A-Za-z0-9]', '-') + ".png")), [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
    }
  }
  ($res | ConvertTo-Json -Depth 6 -Compress) | Out-File -FilePath $Out -Encoding utf8
  "ok"
} finally {
  if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$($proc.Id)" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

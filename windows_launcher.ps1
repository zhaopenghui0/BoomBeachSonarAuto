Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataRoot = if ($env:BBMA_DATA_DIR) { $env:BBMA_DATA_DIR } else { $ProjectRoot }
$BundledRunner = $env:BBMA_WORKER_PATH
$RunScript = Join-Path $ProjectRoot 'run_level.py'
$LogFile = Join-Path $DataRoot '_debug\logs\bbma.log'
$ConsoleLog = Join-Path $DataRoot '_debug\logs\launcher_console.log'
$OutputDir = Join-Path $DataRoot 'outputs'
$script:AutomationProcess = $null
$script:LastConsoleText = ''
$script:LogDisplayStart = 0

function Resolve-PythonCommand {
    $venvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        return @{ FileName = $venvPython; Prefix = '' }
    }
    $py = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        return @{ FileName = $py.Source; Prefix = '-3 ' }
    }
    $python = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @{ FileName = $python.Source; Prefix = '' }
    }
    return $null
}

function Resolve-RunnerCommand {
    if ($BundledRunner -and (Test-Path -LiteralPath $BundledRunner)) {
        return @{ FileName = $BundledRunner; Prefix = ''; Bundled = $true }
    }
    $python = Resolve-PythonCommand
    if ($null -eq $python) {
        return $null
    }
    return @{ FileName = $python.FileName; Prefix = $python.Prefix; Bundled = $false }
}

function Set-RoundedButtonRegion {
    param(
        [System.Windows.Forms.Button]$Button,
        [int]$Radius = 10
    )
    if ($Button.Width -le 0 -or $Button.Height -le 0) {
        return
    }

    $diameter = [Math]::Min($Radius * 2, [Math]::Min($Button.Width, $Button.Height))
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc(0, 0, $diameter, $diameter, 180, 90)
    $path.AddArc($Button.Width - $diameter - 1, 0, $diameter, $diameter, 270, 90)
    $path.AddArc($Button.Width - $diameter - 1, $Button.Height - $diameter - 1, $diameter, $diameter, 0, 90)
    $path.AddArc(0, $Button.Height - $diameter - 1, $diameter, $diameter, 90, 90)
    $path.CloseFigure()

    $oldRegion = $Button.Region
    $Button.Region = New-Object System.Drawing.Region($path)
    if ($null -ne $oldRegion) {
        $oldRegion.Dispose()
    }
    $path.Dispose()
}

function Initialize-ActionButton {
    param(
        [System.Windows.Forms.Button]$Button,
        [System.Drawing.Color]$BackColor,
        [System.Drawing.Color]$ForeColor
    )
    $Button.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $Button.FlatAppearance.BorderSize = 0
    $Button.UseVisualStyleBackColor = $false
    $Button.BackColor = $BackColor
    $Button.ForeColor = $ForeColor
    $Button.Cursor = [System.Windows.Forms.Cursors]::Hand
    Set-RoundedButtonRegion -Button $Button -Radius 10
}

function Read-LauncherLog {
    if (-not (Test-Path -LiteralPath $ConsoleLog)) {
        return ''
    }
    try {
        $text = [System.IO.File]::ReadAllText($ConsoleLog, [System.Text.Encoding]::UTF8)
        if ($script:LogDisplayStart -gt 0) {
            if ($text.Length -ge $script:LogDisplayStart) {
                $text = $text.Substring($script:LogDisplayStart)
            } else {
                $script:LogDisplayStart = 0
            }
        }
        $ansiPattern = [char]27 + '\[[0-9;?]*[ -/]*[@-~]'
        $text = [System.Text.RegularExpressions.Regex]::Replace($text, $ansiPattern, '')
        $text = $text -replace "`r(?!`n)", "`r`n"
        if ($text.Length -gt 120000) {
            $text = $text.Substring($text.Length - 120000)
        }
        return $text
    } catch {
        return $script:LastConsoleText
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = '海岛奇兵声呐助手'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(800, 650)
$form.MinimumSize = New-Object System.Drawing.Size(720, 560)
$form.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10)
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 247, 250)

$title = New-Object System.Windows.Forms.Label
$title.Text = '海岛奇兵声呐助手'
$title.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 20, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(28, 22)
$form.Controls.Add($title)

$tip = New-Object System.Windows.Forms.Label
$tip.Text = '启动模拟器并让游戏停留在主界面，然后选择关卡。任务会在后台运行，日志直接显示在本窗口。'
$tip.AutoSize = $true
$tip.Location = New-Object System.Drawing.Point(32, 68)
$tip.ForeColor = [System.Drawing.Color]::FromArgb(85, 91, 101)
$form.Controls.Add($tip)

$levelLabel = New-Object System.Windows.Forms.Label
$levelLabel.Text = '关卡'
$levelLabel.AutoSize = $true
$levelLabel.Location = New-Object System.Drawing.Point(32, 112)
$form.Controls.Add($levelLabel)

$levelBox = New-Object System.Windows.Forms.ComboBox
$levelBox.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$levelBox.Location = New-Object System.Drawing.Point(82, 106)
$levelBox.Size = New-Object System.Drawing.Size(150, 32)
1..50 | ForEach-Object { [void]$levelBox.Items.Add("第 $_ 关") }
$levelBox.SelectedIndex = 0
$form.Controls.Add($levelBox)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = '开始运行'
$startButton.Location = New-Object System.Drawing.Point(244, 103)
$startButton.Size = New-Object System.Drawing.Size(116, 38)
Initialize-ActionButton -Button $startButton -BackColor ([System.Drawing.Color]::FromArgb(38, 132, 255)) -ForeColor ([System.Drawing.Color]::White)
$form.Controls.Add($startButton)

$logButton = New-Object System.Windows.Forms.Button
$logButton.Text = '打开日志文件'
$logButton.Location = New-Object System.Drawing.Point(374, 103)
$logButton.Size = New-Object System.Drawing.Size(116, 38)
Initialize-ActionButton -Button $logButton -BackColor ([System.Drawing.Color]::White) -ForeColor ([System.Drawing.Color]::FromArgb(31, 41, 55))
$form.Controls.Add($logButton)

$outputButton = New-Object System.Windows.Forms.Button
$outputButton.Text = '打开结果目录'
$outputButton.Location = New-Object System.Drawing.Point(504, 103)
$outputButton.Size = New-Object System.Drawing.Size(116, 38)
Initialize-ActionButton -Button $outputButton -BackColor ([System.Drawing.Color]::White) -ForeColor ([System.Drawing.Color]::FromArgb(31, 41, 55))
$form.Controls.Add($outputButton)

$clearLogButton = New-Object System.Windows.Forms.Button
$clearLogButton.Text = '清空日志'
$clearLogButton.Location = New-Object System.Drawing.Point(634, 103)
$clearLogButton.Size = New-Object System.Drawing.Size(116, 38)
Initialize-ActionButton -Button $clearLogButton -BackColor ([System.Drawing.Color]::FromArgb(229, 231, 235)) -ForeColor ([System.Drawing.Color]::FromArgb(55, 65, 81))
$form.Controls.Add($clearLogButton)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = '状态：等待启动'
$statusLabel.AutoSize = $true
$statusLabel.Location = New-Object System.Drawing.Point(32, 158)
$statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(55, 65, 81)
$form.Controls.Add($statusLabel)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$logBox.WordWrap = $false
$logBox.Font = New-Object System.Drawing.Font('Consolas', 10)
$logBox.BackColor = [System.Drawing.Color]::FromArgb(24, 28, 36)
$logBox.ForeColor = [System.Drawing.Color]::FromArgb(222, 226, 230)
$logBox.Location = New-Object System.Drawing.Point(32, 190)
$logBox.Size = New-Object System.Drawing.Size(718, 390)
$logBox.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Bottom -bor [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right
$logBox.Text = '运行日志将在这里显示，不会再打开黑色命令窗口。'
$form.Controls.Add($logBox)

$startButton.Add_Click({
    if ($null -ne $script:AutomationProcess -and -not $script:AutomationProcess.HasExited) {
        [System.Windows.Forms.MessageBox]::Show('当前已有任务正在运行。', '提示')
        return
    }
    $runner = Resolve-RunnerCommand
    if ($null -eq $runner) {
        [System.Windows.Forms.MessageBox]::Show(
            '未找到内置运行器或 Python。请重新下载完整的免安装版 EXE。',
            '启动失败'
        )
        return
    }
    if (-not $runner.Bundled -and -not (Test-Path -LiteralPath $RunScript)) {
        [System.Windows.Forms.MessageBox]::Show("找不到运行入口：$RunScript", '启动失败')
        return
    }

    $level = $levelBox.SelectedIndex + 1
    $logDir = Split-Path -Parent $ConsoleLog
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    [System.IO.File]::WriteAllText($ConsoleLog, '', [System.Text.UTF8Encoding]::new($false))
    $script:LastConsoleText = ''
    $script:LogDisplayStart = 0
    $logBox.Text = '正在启动，请稍候……'

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $runner.FileName
    if ($runner.Bundled) {
        $psi.Arguments = "--level $level --console-log `"$ConsoleLog`""
    } else {
        $psi.Arguments = "$($runner.Prefix)-u `"$RunScript`" --level $level --console-log `"$ConsoleLog`""
    }
    $psi.WorkingDirectory = $DataRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi.EnvironmentVariables['PYTHONUTF8'] = '1'
    $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'

    try {
        $script:AutomationProcess = [System.Diagnostics.Process]::Start($psi)
        $startButton.Enabled = $false
        $levelBox.Enabled = $false
        $statusLabel.Text = "状态：第 $level 关正在运行"
        $statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(22, 101, 52)
    } catch {
        [System.Windows.Forms.MessageBox]::Show("启动失败：$($_.Exception.Message)", '启动失败')
    }
})

$logButton.Add_Click({
    $path = if (Test-Path -LiteralPath $ConsoleLog) { $ConsoleLog } else { $LogFile }
    if (Test-Path -LiteralPath $path) {
        Start-Process -FilePath 'notepad.exe' -ArgumentList $path
    } else {
        [System.Windows.Forms.MessageBox]::Show('日志文件尚未生成。', '提示')
    }
})

$outputButton.Add_Click({
    if (-not (Test-Path -LiteralPath $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir | Out-Null
    }
    Start-Process -FilePath 'explorer.exe' -ArgumentList $OutputDir
})

$clearLogButton.Add_Click({
    $isRunning = $null -ne $script:AutomationProcess -and -not $script:AutomationProcess.HasExited
    if ($isRunning) {
        try {
            if (Test-Path -LiteralPath $ConsoleLog) {
                $script:LogDisplayStart = [System.IO.File]::ReadAllText(
                    $ConsoleLog,
                    [System.Text.Encoding]::UTF8
                ).Length
            }
        } catch {
            $script:LogDisplayStart = 0
        }
        $statusLabel.Text = '状态：已清空当前显示，任务继续运行'
    } else {
        foreach ($path in @($ConsoleLog, $LogFile)) {
            try {
                $parent = Split-Path -Parent $path
                if (-not (Test-Path -LiteralPath $parent)) {
                    New-Item -ItemType Directory -Path $parent | Out-Null
                }
                [System.IO.File]::WriteAllText($path, '', [System.Text.UTF8Encoding]::new($false))
            } catch {
                [System.Windows.Forms.MessageBox]::Show(
                    "无法清空日志：$path`n$($_.Exception.Message)",
                    '清空失败'
                )
                return
            }
        }
        $script:LogDisplayStart = 0
        $statusLabel.Text = '状态：日志已清空'
    }
    $script:LastConsoleText = ''
    $logBox.Text = '日志已清空。'
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 400
$timer.Add_Tick({
    $text = Read-LauncherLog
    if ($text -ne $script:LastConsoleText) {
        $script:LastConsoleText = $text
        $logBox.Text = $text
        $logBox.SelectionStart = $logBox.TextLength
        $logBox.ScrollToCaret()
    }
    if ($null -ne $script:AutomationProcess -and $script:AutomationProcess.HasExited) {
        $exitCode = $script:AutomationProcess.ExitCode
        $startButton.Enabled = $true
        $levelBox.Enabled = $true
        if ($exitCode -eq 0) {
            $statusLabel.Text = '状态：运行完成'
            $statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(22, 101, 52)
        } else {
            $statusLabel.Text = "状态：运行失败，退出代码 $exitCode"
            $statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(185, 28, 28)
        }
        $script:AutomationProcess.Dispose()
        $script:AutomationProcess = $null
    }
})
$timer.Start()

$form.Add_FormClosing({
    if ($null -ne $script:AutomationProcess -and -not $script:AutomationProcess.HasExited) {
        $choice = [System.Windows.Forms.MessageBox]::Show(
            '任务仍在后台运行。关闭界面不会强制结束任务，是否关闭界面？',
            '任务正在运行',
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Question
        )
        if ($choice -ne [System.Windows.Forms.DialogResult]::Yes) {
            $_.Cancel = $true
        }
    }
})

[void]$form.ShowDialog()

using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Launcher
{
    [STAThread]
    private static void Main()
    {
        string projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        string launcherScript = Path.Combine(projectRoot, "windows_launcher.ps1");

        if (!File.Exists(launcherScript))
        {
            MessageBox.Show(
                "找不到图形启动器：\n" + launcherScript,
                "启动失败",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        string powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.System),
            @"WindowsPowerShell\v1.0\powershell.exe");

        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = powershell,
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + launcherScript + "\"",
                WorkingDirectory = projectRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
            };
            Process.Start(startInfo);
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                "无法启动图形界面：\n" + exception.Message,
                "启动失败",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}

using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

internal static class Launcher
{
    private const string WorkerResource = "BBMA.AutomationWorker";
    private const string ScriptResource = "BBMA.WindowsLauncher";

    [STAThread]
    private static void Main()
    {
        try
        {
            string executableDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string bundleVersion = typeof(Launcher).Module.ModuleVersionId.ToString("N");
            string runtimeDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "BoomBeachSonarAuto",
                "runtime",
                bundleVersion);
            Directory.CreateDirectory(runtimeDirectory);

            string workerPath = Path.Combine(runtimeDirectory, "bbma_worker.exe");
            string scriptPath = Path.Combine(runtimeDirectory, "windows_launcher.ps1");
            ExtractResource(WorkerResource, workerPath);
            ExtractResource(ScriptResource, scriptPath);

            string powershell = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.System),
                @"WindowsPowerShell\v1.0\powershell.exe");
            var startInfo = new ProcessStartInfo
            {
                FileName = powershell,
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + scriptPath + "\"",
                WorkingDirectory = executableDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
            };
            startInfo.EnvironmentVariables["BBMA_WORKER_PATH"] = workerPath;
            startInfo.EnvironmentVariables["BBMA_DATA_DIR"] = executableDirectory;
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

    private static void ExtractResource(string resourceName, string destinationPath)
    {
        Assembly assembly = Assembly.GetExecutingAssembly();
        using (Stream input = assembly.GetManifestResourceStream(resourceName))
        {
            if (input == null)
            {
                throw new InvalidOperationException("内置资源缺失：" + resourceName);
            }

            var existing = new FileInfo(destinationPath);
            if (existing.Exists && existing.Length == input.Length)
            {
                return;
            }

            string temporaryPath = destinationPath + ".tmp";
            using (var output = new FileStream(temporaryPath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                input.CopyTo(output);
            }
            if (File.Exists(destinationPath))
            {
                File.Delete(destinationPath);
            }
            File.Move(temporaryPath, destinationPath);
        }
    }
}

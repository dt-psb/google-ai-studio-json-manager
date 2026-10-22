Option Explicit
On Error Resume Next

Dim WshShell, fso, currentDir, pyExe, logFile

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = currentDir & "\launch_error.log"

WshShell.CurrentDirectory = currentDir

' 1. Check Anaconda Python
If fso.FileExists("C:\ProgramData\anaconda3\pythonw.exe") Then
    pyExe = "C:\ProgramData\anaconda3\pythonw.exe"
ElseIf fso.FileExists("C:\ProgramData\anaconda3\python.exe") Then
    pyExe = "C:\ProgramData\anaconda3\python.exe"
' 2. Check Python 3.12
ElseIf fso.FileExists(WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe") Then
    pyExe = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe"
ElseIf fso.FileExists(WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\python.exe") Then
    pyExe = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\python.exe"
Else
    pyExe = "pythonw.exe"
End If

WshShell.Run """" & pyExe & """ """ & currentDir & "\app.pyw""", 0, False

If Err.Number <> 0 Then
    Dim f
    Set f = fso.OpenTextFile(logFile, 8, True)
    f.WriteLine "[VBS Error] " & Err.Description
    f.Close
    MsgBox "Failed to launch Google AI Studio:" & vbCrLf & Err.Description & vbCrLf & vbCrLf & "Please check app_debug.log and launch_error.log", 16, "Launch Error"
End If

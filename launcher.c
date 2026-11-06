#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    wchar_t appDir[MAX_PATH];
    GetModuleFileNameW(NULL, appDir, MAX_PATH);
    
    wchar_t* lastSlash = wcsrchr(appDir, L'\\');
    if (lastSlash) {
        *lastSlash = L'\0';
    }
    SetCurrentDirectoryW(appDir);

    wchar_t vbsPath[MAX_PATH];
    wsprintfW(vbsPath, L"%s\\launch_app.vbs", appDir);

    wchar_t cmdLine[MAX_PATH * 2];
    wsprintfW(cmdLine, L"wscript.exe \"%s\"", vbsPath);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    ZeroMemory(&pi, sizeof(pi));

    if (CreateProcessW(NULL, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, appDir, &si, &pi)) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 0;
    }

    // Fallback: direct pythonw app.pyw
    wsprintfW(cmdLine, L"pythonw.exe \"%s\\app.pyw\"", appDir);
    if (CreateProcessW(NULL, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, appDir, &si, &pi)) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return 0;
    }

    MessageBoxW(NULL, L"AI Studio Prompt & Chunk Manager를 실행할 수 없습니다.\nPython 또는 launch_app.vbs를 확인해주세요.", L"실행 오류", MB_OK | MB_ICONERROR);
    return 1;
}

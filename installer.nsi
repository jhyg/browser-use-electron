; Browser-Use Agent NSIS Installer Script
!define APP_NAME "Browser-Use Agent"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Process-GPT"
!define APP_URL "https://process-gpt.io"

; Basic settings
Name "${APP_NAME}"
OutFile "browser-use-agent-setup.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "InstallPath"
RequestExecutionLevel admin

; Interface settings
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Install pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\browser-use-agent.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Run Browser-Use Agent after installation (Recommended)"
!insertmacro MUI_PAGE_FINISH

; Uninstall pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; Install section
Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  
  ; Copy all files
  File /r "dist\browser-use-agent-win32-x64\*.*"
  
  ; Register protocol handler
  WriteRegStr HKCU "Software\Classes\browser-use-agent" "" "URL:browser-use-agent"
  WriteRegStr HKCU "Software\Classes\browser-use-agent" "URL Protocol" ""
  WriteRegStr HKCU "Software\Classes\browser-use-agent\DefaultIcon" "" "$INSTDIR\browser-use-agent.exe,0"
  WriteRegStr HKCU "Software\Classes\browser-use-agent\shell\open\command" "" '"$INSTDIR\browser-use-agent.exe" "%1"'
  
  ; Start menu shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\browser-use-agent.exe"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  
  ; Uninstaller registry
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\browser-use-agent.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "URLInfoAbout" "${APP_URL}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
  
  ; Save install path
  WriteRegStr HKLM "Software\${APP_NAME}" "InstallPath" "$INSTDIR"
  
  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Uninstall section
Section "Uninstall"
  ; Remove files
  RMDir /r "$INSTDIR"
  
  ; Remove registry
  DeleteRegKey HKCU "Software\Classes\browser-use-agent"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegKey HKLM "Software\${APP_NAME}"
  
  ; Remove start menu shortcuts
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
SectionEnd 
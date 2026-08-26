; ============================================================
; Bot Udziały - Wyszukiwarka :: NSIS Installer Script v2
; MUI2 based, RequestExecutionLevel user (no admin)
; ============================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

; --- General ---
Name "Bot Udziały - Wyszukiwarka"
OutFile "${OUTPUT_DIR}\UdzialyBot-Setup.exe"
InstallDir "C:\UdzialyBot"
InstallDirRegKey HKCU "Software\BotUdzialy" "InstallDir"
RequestExecutionLevel user
Unicode true

; --- Branding ---
!define PRODUCT_NAME "Bot Udziały - Wyszukiwarka"
!define PRODUCT_PUBLISHER "QA10 sp. z o.o."
!define PRODUCT_VERSION "2.0.0"

; --- MUI Settings ---
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; --- Finish Page Settings ---
!define MUI_FINISHPAGE_RUN "$INSTDIR\setup_env.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Uruchom konfigurację"
!define MUI_FINISHPAGE_RUN_NOTCHECKED

; --- Pages ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; --- Language ---
!insertmacro MUI_LANGUAGE "Polish"

; ============================================================
; SECTIONS
; ============================================================

Section "Python 3.11.9" SecPython
    SectionIn RO
    SetOutPath "$TEMP"
    File "${PROJECT_BUNDLE}\python-3.11.9-amd64.exe"
    
    ; Silent install Python to $INSTDIR\python
    ExecWait '"$TEMP\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 TargetDir=$INSTDIR\python Include_pip=1 Include_tcltk=1 Include_test=0 Include_doc=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 PrependPath=0 CompileAll=0'
    
    Delete "$TEMP\python-3.11.9-amd64.exe"
SectionEnd

Section "Tor Network" SecTor
    SectionIn RO
    SetOutPath "$INSTDIR\tor"
    File /r "${PROJECT_BUNDLE}\tor\*.*"
SectionEnd

Section "Kod źródłowy" SecSource
    SectionIn RO
    
    ; bot/
    SetOutPath "$INSTDIR\bot"
    File /r "${PROJECT_BUNDLE}\bot\*.*"
    
    ; scraper/
    SetOutPath "$INSTDIR\scraper"
    File /r "${PROJECT_BUNDLE}\scraper\*.*"
    
    ; detector/
    SetOutPath "$INSTDIR\detector"
    File /r "${PROJECT_BUNDLE}\detector\*.*"
    
    ; storage/
    SetOutPath "$INSTDIR\storage"
    File /r "${PROJECT_BUNDLE}\storage\*.*"
    
    ; geo/
    SetOutPath "$INSTDIR\geo"
    File /r "${PROJECT_BUNDLE}\geo\*.*"
    
    ; data/
    SetOutPath "$INSTDIR\data"
    File /r "${PROJECT_BUNDLE}\data\*.*"
SectionEnd

Section "Pliki konfiguracyjne" SecConfig
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "${PROJECT_BUNDLE}\config_wizard.pyw"
    File "${PROJECT_BUNDLE}\requirements.txt"
    File "${PROJECT_BUNDLE}\launcher.pyw"
    File "${PROJECT_BUNDLE}\stop_bot.bat"
    File "${PROJECT_BUNDLE}\setup_env.bat"
    
    ; torrc
    SetOutPath "$INSTDIR\tor"
    File "${PROJECT_BUNDLE}\tor\torrc"
SectionEnd

; ============================================================
; POST-INSTALL: Shortcuts & Uninstaller
; ============================================================

Section "-Post" SecPost
    ; Save install dir to registry
    WriteRegStr HKCU "Software\BotUdzialy" "InstallDir" "$INSTDIR"
    
    ; --- Start Menu ---
    CreateDirectory "$SMPROGRAMS\Bot Udziały"
    CreateShortCut "$SMPROGRAMS\Bot Udziały\Uruchom Bota.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\launcher.pyw"' "$INSTDIR\python\pythonw.exe" 0
    CreateShortCut "$SMPROGRAMS\Bot Udziały\Konfiguracja.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\config_wizard.pyw"' "$INSTDIR\python\pythonw.exe" 0
    CreateShortCut "$SMPROGRAMS\Bot Udziały\Zatrzymaj.lnk" "$INSTDIR\stop_bot.bat" "" "$INSTDIR\stop_bot.bat" 0
    CreateShortCut "$SMPROGRAMS\Bot Udziały\Odinstaluj.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
    
    ; --- Desktop Shortcut ---
    CreateShortCut "$DESKTOP\Bot Udziały.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\launcher.pyw"' "$INSTDIR\python\pythonw.exe" 0
    
    ; --- Uninstaller ---
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    ; Add/Remove Programs entry
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy" "NoRepair" 1
SectionEnd

; ============================================================
; UNINSTALLER
; ============================================================

Section "Uninstall"
    ; Remove Python (run uninstaller)
    IfFileExists "$INSTDIR\python\python.exe" 0 +2
        ExecWait '"$INSTDIR\python\python.exe" -B -c "import subprocess,sys;subprocess.run([sys.executable.replace(chr(92)+chr(112)+chr(121)+chr(116)+chr(104)+chr(111)+chr(110)+chr(46)+chr(101)+chr(120)+chr(101),chr(92)+chr(117)+chr(110)+chr(105)+chr(110)+chr(115)+chr(116)+chr(97)+chr(108)+chr(108)+chr(46)+chr(101)+chr(120)+chr(101)]),chr(47)+chr(113)+chr(117)+chr(105)+chr(101)+chr(116)])"'
    
    ; Remove files
    RMDir /r "$INSTDIR\bot"
    RMDir /r "$INSTDIR\scraper"
    RMDir /r "$INSTDIR\detector"
    RMDir /r "$INSTDIR\storage"
    RMDir /r "$INSTDIR\geo"
    RMDir /r "$INSTDIR\data"
    RMDir /r "$INSTDIR\tor"
    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\tests"
    
    Delete "$INSTDIR\config_wizard.pyw"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\launcher.pyw"
    Delete "$INSTDIR\stop_bot.bat"
    Delete "$INSTDIR\setup_env.bat"
    Delete "$INSTDIR\config.yaml"
    Delete "$INSTDIR\uninstall.exe"
    
    RMDir "$INSTDIR"
    
    ; Remove shortcuts
    Delete "$SMPROGRAMS\Bot Udziały\Uruchom Bota.lnk"
    Delete "$SMPROGRAMS\Bot Udziały\Konfiguracja.lnk"
    Delete "$SMPROGRAMS\Bot Udziały\Zatrzymaj.lnk"
    Delete "$SMPROGRAMS\Bot Udziały\Odinstaluj.lnk"
    RMDir "$SMPROGRAMS\Bot Udziały"
    Delete "$DESKTOP\Bot Udziały.lnk"
    
    ; Remove registry
    DeleteRegKey HKCU "Software\BotUdzialy"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BotUdzialy"
SectionEnd

; ============================================================================
; Udzialy Bot - NSIS Installer Script
; Product: Udzialy Bot - Wyszukiwarka Udzialow
; Publisher: QA10 sp. z o.o.
; ============================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; ============================================================================
; General Configuration
; ============================================================================
!define PRODUCT_NAME "Udzialy Bot - Wyszukiwarka Udzialow"
!define PRODUCT_SHORT "UdzialyBot"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "QA10 sp. z o.o."
!define PRODUCT_WEB_SITE "https://qa10.pl"
!define INSTALL_DIR "C:\UdzialyBot"
!define UNINSTALL_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_SHORT}"

; Build directory (passed from build.sh via -D flag)
!ifndef BUILD_DIR
    !define BUILD_DIR "build"
!endif

Name "${PRODUCT_NAME}"
OutFile "Output\UdzialyBot-Setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "${UNINSTALL_REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 32
Unicode true

; ============================================================================
; MUI2 Configuration
; ============================================================================
!define MUI_ABORTWARNING
!define MUI_ICON "${BUILD_DIR}\icon.ico"
!define MUI_UNICON "${BUILD_DIR}\icon.ico"

; Branding
!define MUI_WELCOMEPAGE_TITLE "Witamy w instalatorze ${PRODUCT_NAME}"
!define MUI_WELCOMEPAGE_TEXT "Ten kreator zainstaluje ${PRODUCT_NAME} na Twoim komputerze.$\r$\n$\r$\nProgram automatycznie:$\r$\n- Zainstaluje srodowisko Python$\r$\n- Pobierze wymagane biblioteki$\r$\n- Skonfiguruje przegladarke Chromium$\r$\n- Uruchomi kreator konfiguracji$\r$\n$\r$\nKliknij Dalej, aby kontynuowac."

!define MUI_FINISHPAGE_RUN "$INSTDIR\setup_env.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Uruchom konfiguracje (wymagane przy pierwszej instalacji)"
!define MUI_FINISHPAGE_RUN_CHECKED

; ============================================================================
; Pages
; ============================================================================
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${BUILD_DIR}\app\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ============================================================================
; Languages
; ============================================================================
!insertmacro MUI_LANGUAGE "Polish"
!insertmacro MUI_LANGUAGE "English"

; ============================================================================
; Installer Sections
; ============================================================================
Section "Glowne pliki" SecMain
    SectionIn RO  ; Required section

    SetOutPath "$INSTDIR"

    ; --- Python Embedded ---
    DetailPrint "Instalowanie Python..."
    SetOutPath "$INSTDIR\python"
    File /r "${BUILD_DIR}\python\*.*"

    ; --- Wheels ---
    DetailPrint "Kopiowanie bibliotek Python..."
    SetOutPath "$INSTDIR\wheels"
    File /nonfatal /r "${BUILD_DIR}\wheels\*.*"

    ; --- Tor Expert Bundle ---
    DetailPrint "Instalowanie Tor..."
    SetOutPath "$INSTDIR\tor"
    File /r "${BUILD_DIR}\tor\*.*"

    ; --- Application Source ---
    DetailPrint "Kopiowanie aplikacji..."
    SetOutPath "$INSTDIR\app"
    File /r "${BUILD_DIR}\app\*.*"

    ; --- Support Scripts ---
    SetOutPath "$INSTDIR"
    File "${BUILD_DIR}\setup_env.bat"
    File "${BUILD_DIR}\start_bot.bat"
    File "${BUILD_DIR}\stop_bot.bat"
    File "${BUILD_DIR}\config_wizard.pyw"
    File /nonfatal "${BUILD_DIR}\icon.ico"

    ; --- Create Tor data directory ---
    CreateDirectory "$INSTDIR\tor\data"

    ; --- Write uninstaller ---
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; --- Registry entries ---
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "DisplayIcon" "$INSTDIR\icon.ico"
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegStr HKLM "${UNINSTALL_REG_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegDWORD HKLM "${UNINSTALL_REG_KEY}" "NoModify" 1
    WriteRegDWORD HKLM "${UNINSTALL_REG_KEY}" "NoRepair" 1

    ; Calculate installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${UNINSTALL_REG_KEY}" "EstimatedSize" $0

SectionEnd

; ============================================================================
; Shortcuts
; ============================================================================
Section "Skroty" SecShortcuts
    ; --- Start Menu ---
    CreateDirectory "$SMPROGRAMS\${PRODUCT_SHORT}"

    ; Uruchom Bota
    CreateShortCut "$SMPROGRAMS\${PRODUCT_SHORT}\Uruchom Bota.lnk" \
        "$INSTDIR\start_bot.bat" "" "$INSTDIR\icon.ico" 0

    ; Konfiguracja
    CreateShortCut "$SMPROGRAMS\${PRODUCT_SHORT}\Konfiguracja.lnk" \
        "$INSTDIR\python\pythonw.exe" '"$INSTDIR\config_wizard.pyw"' \
        "$INSTDIR\icon.ico" 0

    ; Zatrzymaj Bota
    CreateShortCut "$SMPROGRAMS\${PRODUCT_SHORT}\Zatrzymaj Bota.lnk" \
        "$INSTDIR\stop_bot.bat" "" "$INSTDIR\icon.ico" 0

    ; Uninstall
    CreateShortCut "$SMPROGRAMS\${PRODUCT_SHORT}\Odinstaluj.lnk" \
        "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0

    ; --- Desktop shortcut ---
    CreateShortCut "$DESKTOP\Udzialy Bot.lnk" \
        "$INSTDIR\start_bot.bat" "" "$INSTDIR\icon.ico" 0

SectionEnd

; ============================================================================
; Uninstaller
; ============================================================================
Section "Uninstall"
    ; Kill running processes
    nsExec::ExecToLog 'taskkill /IM python.exe /F'
    nsExec::ExecToLog 'taskkill /IM tor.exe /F'

    ; Remove files
    RMDir /r "$INSTDIR\python"
    RMDir /r "$INSTDIR\wheels"
    RMDir /r "$INSTDIR\tor"
    RMDir /r "$INSTDIR\app"
    RMDir /r "$INSTDIR\.venv"
    Delete "$INSTDIR\setup_env.bat"
    Delete "$INSTDIR\start_bot.bat"
    Delete "$INSTDIR\stop_bot.bat"
    Delete "$INSTDIR\config_wizard.pyw"
    Delete "$INSTDIR\config.yaml"
    Delete "$INSTDIR\icon.ico"
    Delete "$INSTDIR\uninstall.exe"

    ; Remove shortcuts
    RMDir /r "$SMPROGRAMS\${PRODUCT_SHORT}"
    Delete "$DESKTOP\Udzialy Bot.lnk"

    ; Remove registry
    DeleteRegKey HKLM "${UNINSTALL_REG_KEY}"

    ; Remove install directory (if empty)
    RMDir "$INSTDIR"

    DetailPrint "Dezinstalacja zakonczona."
SectionEnd

; ============================================================================
; Functions
; ============================================================================
Function .onInit
    ; Check Windows version (require Windows 10+)
    ; Set language to Polish by default
FunctionEnd

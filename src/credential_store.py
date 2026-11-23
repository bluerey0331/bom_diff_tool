"""Store API credentials in the current user's Windows Credential Manager."""

import json
import sys

from src.ui_language import tr

TARGET = "BOM Diff Tool/API credentials"


def read_credentials() -> dict[str, str] | None:
    if sys.platform != "win32":
        return None
    from win32ctypes.pywin32 import pywintypes, win32cred

    try:
        entry = win32cred.CredRead(TARGET, win32cred.CRED_TYPE_GENERIC)
    except pywintypes.error as error:
        if error.winerror == 1168:  # ERROR_NOT_FOUND
            return None
        raise OSError(error.winerror, error.strerror) from error
    blob = entry["CredentialBlob"]
    return json.loads(blob.decode("utf-16-le") if isinstance(blob, bytes) else blob)


def write_credentials(values: dict[str, str]) -> None:
    if sys.platform != "win32":
        raise OSError(tr("認証情報の保存にはWindowsが必要です。",
                         "Credential storage requires Windows."))
    from win32ctypes.pywin32 import pywintypes, win32cred

    try:
        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": TARGET,
            "UserName": "BOM Diff Tool",
            "CredentialBlob": json.dumps(values, ensure_ascii=True),
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        })
    except pywintypes.error as error:
        raise OSError(error.winerror, error.strerror) from error

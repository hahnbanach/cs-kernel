"""Read-only Google Drive access for the operator (headless).

Uses the SAME service-account key as the Firebase mint (``firebase_sa_path``
in :mod:`cs.config`) but with a Drive scope. **No domain-wide delegation**:
the service account reads only the files/folders explicitly **shared with its
address** (printed by ``drive ls`` when nothing is shared) as Viewer — the
least-privilege "Path B" model. To widen access, share more folders with that
address in Google Drive; nothing in this module changes.

Drive API must be enabled on the key's project; a 403 ``SERVICE_DISABLED``
from any call means it is not — the error body carries the enable URL.

CLI self-test (the way the operator runs it):

    .venv/bin/python -m cs.drive ls            # everything shared with the SA
    .venv/bin/python -m cs.drive ls <folderId> # a folder's children
    .venv/bin/python -m cs.drive search "<text>"      # full-text in THIS project's drive ([drive].scope / CS_DRIVE)
    .venv/bin/python -m cs.drive search "<text>" all  # full-text across every drive the SA sees (test override)
    .venv/bin/python -m cs.drive cat <fileId>  # a file's text (Docs/Sheets exported)
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .config import Settings, load

DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
_FILES_URL = "https://www.googleapis.com/drive/v3/files"
_DRIVES_URL = "https://www.googleapis.com/drive/v3/drives"
_FILE_FIELDS = "id,name,mimeType,owners(emailAddress),parents,modifiedTime,size,trashed"
_LIST_FIELDS = f"nextPageToken,files({_FILE_FIELDS})"

# Google-native types cannot be downloaded raw — they must be exported; pick a
# text-ish target so the operator gets readable content.
_EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


class DriveError(RuntimeError):
    """A Drive API call failed; the message carries the status and body."""


class DriveClient:
    """Thin read-only Drive v3 client over the service-account key."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load()
        self._creds = service_account.Credentials.from_service_account_file(
            self.settings.firebase_sa_path, scopes=[DRIVE_READONLY]
        )

    @property
    def service_account_email(self) -> str:
        return self._creds.service_account_email

    # --- auth ---
    def _token(self) -> str:
        if not self._creds.valid:
            self._creds.refresh(Request())
        return self._creds.token

    def _get(self, url: str, params: dict, *, timeout: int = 30) -> requests.Response:
        params = {"supportsAllDrives": True, **params}
        r = requests.get(url, headers={"Authorization": "Bearer " + self._token()}, params=params, timeout=timeout)
        if r.status_code != 200:
            raise DriveError(f"Drive API {r.status_code} for {url}\n{r.text[:800]}")
        return r

    # --- listing (fetches ALL pages — never capped) ---
    def search(self, q: str, drive_id: str | None = None, page_size: int = 100) -> list[dict]:
        out: list[dict] = []
        token: str | None = None
        while True:
            params = {
                "q": q,
                "fields": _LIST_FIELDS,
                "pageSize": page_size,
                "includeItemsFromAllDrives": True,
            }
            # A Shared Drive is scoped by its id; otherwise span everything visible.
            if drive_id:
                params["corpora"] = "drive"
                params["driveId"] = drive_id
            else:
                params["corpora"] = "allDrives"
            if token:
                params["pageToken"] = token
            data = self._get(_FILES_URL, params).json()
            out.extend(data.get("files", []))
            token = data.get("nextPageToken")
            if not token:
                return out

    def list_drives(self) -> list[dict]:
        """Shared Drives (Team Drives) the service account is a member of."""
        out: list[dict] = []
        token: str | None = None
        while True:
            params = {"fields": "nextPageToken,drives(id,name)", "pageSize": 100}
            if token:
                params["pageToken"] = token
            data = self._get(_DRIVES_URL, params).json()
            out.extend(data.get("drives", []))
            token = data.get("nextPageToken")
            if not token:
                return out

    def list_shared(self) -> list[dict]:
        """My-Drive files shared individually with the SA (not Shared Drives)."""
        return self.search("sharedWithMe=true and trashed=false")

    def list_folder(self, folder_id: str, drive_id: str | None = None) -> list[dict]:
        """Children of a folder; pass ``drive_id`` for an item inside a Shared Drive
        (the Shared Drive's root folder id == the drive id)."""
        return self.search(f"'{folder_id}' in parents and trashed=false", drive_id=drive_id)

    # --- reading ---
    def get_metadata(self, file_id: str) -> dict:
        return self._get(f"{_FILES_URL}/{file_id}", {"fields": _FILE_FIELDS}).json()

    def download(self, file_id: str) -> bytes:
        """Raw bytes of an uploaded (non-Google-native) file."""
        return self._get(f"{_FILES_URL}/{file_id}", {"alt": "media"}, timeout=60).content

    def export(self, file_id: str, mime_type: str) -> bytes:
        """Export a Google-native file (Docs/Sheets/Slides) to ``mime_type``."""
        return self._get(f"{_FILES_URL}/{file_id}/export", {"mimeType": mime_type}, timeout=60).content

    def read_text(self, file_id: str) -> str:
        """Best-effort text of a file: export Google-native, extract PDF/Office text, decode the rest.

        Binary formats can't just be UTF-8 decoded (every invalid byte → U+FFFD),
        so ``cat`` used to emit garbage on them. We handle the ones that actually
        show up in the company drive: PDFs via ``pdftotext`` (poppler); **uploaded
        Office files** (``.xlsx`` / ``.docx`` — Office Open XML, i.e. zipped XML)
        via stdlib extraction (no openpyxl/python-docx needed). Without this the
        P&L / nota-spese spreadsheets were unreadable. Non-PDF, non-Office,
        non-Google-native files are still decoded as text.
        """
        mime = self.get_metadata(file_id).get("mimeType", "")
        export_as = _EXPORT_MIME.get(mime)
        if export_as:
            return self.export(file_id, export_as).decode("utf-8", errors="replace")
        raw = self.download(file_id)
        if mime == "application/pdf" or raw[:5] == b"%PDF-":
            return _pdf_to_text(raw)
        is_zip = raw[:2] == b"PK"
        if mime.endswith("spreadsheetml.sheet") or (is_zip and _zip_has(raw, "xl/workbook.xml")):
            return _xlsx_to_text(raw)
        if mime.endswith("wordprocessingml.document") or (is_zip and _zip_has(raw, "word/document.xml")):
            return _docx_to_text(raw)
        return raw.decode("utf-8", errors="replace")


def _pdf_to_text(raw: bytes) -> str:
    """Extract text from a PDF's raw bytes via the system ``pdftotext`` (poppler).

    Reads the PDF from stdin and writes text to stdout (``- -``), ``-layout`` to
    keep tabular figures aligned. Returns a clear marker (never raw bytes) when
    poppler is missing or the PDF yields no text (scanned / encrypted / malformed).
    """
    exe = shutil.which("pdftotext")
    if not exe:
        return ("[cs.drive: PDF binario, testo non estratto — installa poppler-utils "
                "(pdftotext) per leggerlo, oppure usa DriveClient.download()]")
    try:
        proc = subprocess.run([exe, "-layout", "-", "-"], input=raw,
                              capture_output=True, timeout=120)
    except Exception as e:  # pragma: no cover - subprocess/OS failure
        return f"[cs.drive: estrazione PDF fallita ({e})]"
    text = proc.stdout.decode("utf-8", errors="replace").strip()
    if text:
        return text
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    return ("[cs.drive: nessun testo estraibile dal PDF (probabile scansione o PDF "
            f"cifrato/malformato){'; ' + err if err else ''}]")


# --- Office Open XML (.xlsx / .docx) text extraction, stdlib-only ------------
# The SA has no openpyxl / python-docx; OOXML files are just zips of XML, so we
# pull text straight from the parts. Without this, ``cat`` on an uploaded .xlsx
# returned raw zip bytes (mojibake) — e.g. the P&L pluriennale was unreadable.
_SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_WP = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _zip_has(raw: bytes, name: str) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return name in z.namelist()
    except zipfile.BadZipFile:
        return False


def _col_index(ref: str) -> int:
    """Cell ref column -> 0-based index ('B12' -> 1, 'AA3' -> 26)."""
    idx = 0
    for ch in ref:
        if not ch.isalpha():
            break
        idx = idx * 26 + (ord(ch.upper()) - 64)
    return max(idx - 1, 0)


def _xlsx_to_text(raw: bytes) -> str:
    """Every sheet of an .xlsx as column-aligned TSV (shared strings + cached values)."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = set(z.namelist())
            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.findall(f"{_SS}si"):
                    shared.append("".join(t.text or "" for t in si.iter(f"{_SS}t")))
            rel_target: dict[str, str] = {}
            if "xl/_rels/workbook.xml.rels" in names:
                for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
                    rel_target[r.get("Id")] = r.get("Target", "")
            sheets: list[tuple[str, str]] = []  # (name, part path)
            if "xl/workbook.xml" in names:
                for sh in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{_SS}sheet"):
                    tgt = rel_target.get(sh.get(f"{_REL}id"), "")
                    if tgt:
                        sheets.append((sh.get("name", "?"),
                                       tgt[1:] if tgt.startswith("/") else "xl/" + tgt))
            if not sheets:  # fallback: worksheet parts in name order
                sheets = [(n.rsplit("/", 1)[-1], n)
                          for n in sorted(names) if n.startswith("xl/worksheets/sheet")]
            out: list[str] = []
            for name, path in sheets:
                if path not in names:
                    continue
                out.append(f"# Foglio: {name}")
                for row in ET.fromstring(z.read(path)).iter(f"{_SS}row"):
                    cells: dict[int, str] = {}
                    for c in row.findall(f"{_SS}c"):
                        t, v = c.get("t"), c.find(f"{_SS}v")
                        if t == "s" and v is not None and v.text is not None:
                            i = int(v.text)
                            val = shared[i] if i < len(shared) else ""
                        elif t == "inlineStr":
                            is_ = c.find(f"{_SS}is")
                            val = "".join(x.text or "" for x in is_.iter(f"{_SS}t")) if is_ is not None else ""
                        else:
                            val = v.text if v is not None and v.text is not None else ""
                        if val:
                            cells[_col_index(c.get("r", ""))] = val.replace("\t", " ").replace("\n", " ")
                    if cells:
                        out.append("\t".join(cells.get(i, "") for i in range(max(cells) + 1)))
            return "\n".join(out).strip() or "[cs.drive: .xlsx senza contenuto testuale]"
    except Exception as e:  # pragma: no cover - malformed/edge file
        return f"[cs.drive: estrazione .xlsx fallita ({e})]"


def _docx_to_text(raw: bytes) -> str:
    """Paragraph (and table-cell) text from a .docx, document order."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except Exception as e:  # pragma: no cover
        return f"[cs.drive: estrazione .docx fallita ({e})]"
    lines: list[str] = []
    for p in root.iter(f"{_WP}p"):
        parts: list[str] = []
        for node in p.iter():
            if node.tag == f"{_WP}t":
                parts.append(node.text or "")
            elif node.tag == f"{_WP}tab":
                parts.append("\t")
        lines.append("".join(parts))
    return "\n".join(lines).strip() or "[cs.drive: .docx senza testo]"


def _fmt(f: dict) -> str:
    return f"  {f.get('mimeType', '?'):46.46} {f.get('id')}  {f.get('name')}"


def _resolve_drive(cli: DriveClient, selector: str) -> tuple[str | None, str]:
    """Map a Shared-Drive selector to (drive_id, human label).

    ``selector`` is a Shared Drive **id**, its **name** (the configured
    [drive].scope), a distinctive **substring** of the name, or the explicit
    keyword ``all`` / ``*`` to span every drive the SA can
    see — the ONLY way to leave a single drive's scope. Returns
    ``drive_id=None`` solely for that explicit ``all``; every other selector
    stays pinned to one drive.

    Raises :class:`DriveError` when the selector matches no visible drive (or is
    ambiguous), instead of silently passing it through as a literal driveId —
    which only surfaced later as a cryptic ``Shared drive not found`` 404.
    """
    s = (selector or "").strip()
    if s.lower() in ("all", "*", "alldrives"):
        return None, "TUTTI i Drive visibili al SA (override esplicito)"
    names = {d["id"]: d["name"] for d in cli.list_drives()}
    if s in names:                                    # exact id
        return s, f"Shared Drive '{names[s]}'"
    by_name = {n.lower(): i for i, n in names.items()}
    if s.lower() in by_name:                          # exact name (case-insensitive)
        i = by_name[s.lower()]
        return i, f"Shared Drive '{names[i]}'"
    hits = [i for i, n in names.items() if s.lower() in n.lower()]  # distinctive substring
    if len(hits) == 1:
        return hits[0], f"Shared Drive '{names[hits[0]]}'"
    visible = ", ".join(sorted(names.values())) or "(nessuno condiviso col SA)"
    if not hits:
        raise DriveError(
            f"nessuno Shared Drive corrisponde a '{selector}'. "
            f"Drive visibili al SA: {visible}. Usa nome/id esatto, o 'all' per cercare ovunque."
        )
    raise DriveError(
        f"'{selector}' e' ambiguo: corrisponde a {', '.join(names[i] for i in hits)}. "
        f"Specifica il nome o l'id esatto."
    )


def main(argv: list[str]) -> int:
    cli = DriveClient()
    cmd = argv[0] if argv else "ls"
    try:
        if cmd == "ls":
            if len(argv) > 1:
                target = argv[1]
                drives = {d["id"] for d in cli.list_drives()}
                # if the arg is a Shared Drive id, scope to it; else treat as a folder
                files = cli.list_folder(target, drive_id=target if target in drives else None)
                if not files:
                    print("(cartella vuota o non accessibile)")
                    return 0
                print(f"{len(files)} file:")
                for f in files:
                    print(_fmt(f))
                return 0
            drives = cli.list_drives()
            shared = cli.list_shared()
            if not drives and not shared:
                print("(niente) — condividi una cartella o un Drive condiviso con questo indirizzo (Visualizzatore):")
                print(f"  {cli.service_account_email}")
                return 0
            if drives:
                print(f"Shared Drives ({len(drives)}):")
                for d in drives:
                    print(f"  [drive] {d['id']}  {d['name']}")
            if shared:
                print(f"File condivisi singolarmente ({len(shared)}):")
                for f in shared:
                    print(_fmt(f))
            return 0
        if cmd == "search":
            default_scope = cli.settings.drive_scope
            if len(argv) < 2 or not argv[1].strip():
                print('uso: python -m cs.drive search "<testo full-text>" [driveId|nomeDrive|all]')
                print(f"  default: cerca SOLO nello Shared Drive del progetto "
                      f"(CS_DRIVE={default_scope or '<non impostato>'}).")
                print("  passa un altro drive (id o nome) per cambiarlo, oppure 'all' per cercare in")
                print("  TUTTI i Drive visibili al SA (override esplicito, es. test).")
                return 2
            text = argv[1]
            # explicit 2nd arg wins; otherwise pin to the project's Shared Drive (config).
            selector = argv[2].strip() if len(argv) > 2 and argv[2].strip() else default_scope
            if not selector:
                # Scope message built from Settings — the per-company content
                # here is config, not code (prog name + state dir + scope).
                prog = cli.settings.prog_name or "cs"
                print(f"ERRORE: nessuno Shared Drive di default ne' passato a mano — "
                      f"{prog} resta confinato allo Shared Drive del progetto.", file=sys.stderr)
                print(f"  imposta [drive].scope nel manifest.toml (o CS_DRIVE=<nome|id> in "
                      f"{cli.settings.state_dir}/.env), o passa il drive (o 'all').",
                      file=sys.stderr)
                return 2
            drive_id, scope = _resolve_drive(cli, selector)
            # Drive API full-text; escape backslashes then single-quotes for the q-string.
            safe = text.replace("\\", "\\\\").replace("'", "\\'")
            files = cli.search(f"fullText contains '{safe}' and trashed=false", drive_id=drive_id)
            if not files:
                print(f'(nessun file con "{text}" in {scope})')
                return 0
            print(f'{len(files)} file con "{text}" in {scope}:')
            for f in files:
                print(_fmt(f))
            return 0
        if cmd == "cat":
            if len(argv) < 2:
                print("uso: python -m cs.drive cat <fileId>")
                return 2
            print(cli.read_text(argv[1]))
            return 0
    except DriveError as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        return 1
    print('verbi: ls [folderId] | search "<testo>" [driveId|nomeDrive|all] | cat <fileId>')
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

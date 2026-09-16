"""
Shared curl wrapper for every network-touching script.

All fetching in this repo shells out to the `curl` binary rather than a Python
HTTP library — a deliberate choice: several sources (Google Sheets export,
ChinaShipBuild, marinetraffic.org) block or degrade non-browser clients, and
curl with a browser User-Agent has been the reliable path since the May 2026
pilot. The cost is a system dependency that pip can't declare, so this module
checks for curl up front and fails with an actionable message instead of a
raw FileNotFoundError.

Library usage:
    from fetch import download, fetch_text, fetch_page, CHROME_UA, FetchError

    download(url, out_path, timeout=60)          # save body to a file
    status, body = fetch_text(url, timeout=30)   # ("200", "<html>...")
    page = fetch_page(url)                       # Page(status, text, content_type,
                                                 #      final_url, is_pdf, ...)

`fetch_page` is the rich form the §3.8 verifier uses (ported 2026-09-16 from
the terminals/pipelines verifiers' fetch layers):
  - `--compressed`: some CDNs gzip the body regardless of request headers;
    without it the body decodes to garbage and a live page fails its content
    check.
  - PDF bodies (content-type, `.pdf` path, or `%PDF-` magic) are run through
    `pdftotext -layout` (pypdf fallback, tesseract OCR for scanned PDFs) so a
    DART/Bursa filing or a class-society PDF is verified on its TEXT, not on
    binary soup. A `.pdf` URL that returns HTML is an interstitial and is
    handed downstream as HTML.
  - Charset: honour the Content-Type charset, then the page's own <meta
    charset>, widening gb2312/gbk -> gb18030 and euc-kr -> cp949 (Chinese/
    Korean yard and press pages routinely declare the narrow one). Only then
    fall back to utf-8-with-replacement.
  - Retries: an SSL handshake failure retries once with `-k` (labelled
    `insecure_tls` — the bytes are real, the host identity was not verified);
    a 000/empty-body response retries once WITHOUT the browser UA (a few hosts
    abort on a Chrome UA and serve curl's default fine).
"""
import codecs
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# One canonical browser UA for the whole repo. pull_backend/csb_fetch used a
# bare "Mozilla/5.0" and url_verifier/imo_tracker a full Chrome string; the
# full string works everywhere the bare one did.
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_CURL_INSTALL_HINT = (
    "curl not found on PATH. Install it and re-run:\n"
    "  macOS:         xcode-select --install  (or `brew install curl`)\n"
    "  Debian/Ubuntu: sudo apt install curl\n"
    "  Windows:       ships with Windows 10+; otherwise winget install curl"
)

# A PDF whose text layer yields fewer characters than this is treated as a scan
# and sent to OCR (image-only PDFs often still carry a few stray characters
# from stamps or form fields). OCR is slow (~1-2 s/page) so it is capped.
_PDF_TEXT_MIN = 200
_OCR_MAX_PAGES = 25

# curl exit codes that mean the TLS handshake failed (not that the page is gone).
_CURL_SSL_EXITS = {35, 51, 58, 59, 60, 77, 83, 90, 91}

_META_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)
# gb2312/gbk are proper subsets of gb18030 and euc-kr of cp949; pages declare
# the narrow one and serve characters outside it. Widening is always safe.
_CHARSET_WIDEN = {"gb2312": "gb18030", "gbk": "gb18030", "gb_2312-80": "gb18030",
                  "euc-cn": "gb18030", "big5": "big5hkscs", "big5-hkscs": "big5hkscs",
                  "euc-kr": "cp949", "ks_c_5601-1987": "cp949", "ksc5601": "cp949"}


class FetchError(RuntimeError):
    pass


@dataclass
class Page:
    """One fetched URL. `text` is always the best available TEXT rendering of
    the body (HTML source for HTML; extracted text for PDFs)."""
    status: str                 # HTTP status as a string; "000" = transport failure
    text: str
    content_type: str = ""
    final_url: str = ""         # after redirects (curl -L); "" if unknown
    is_pdf: bool = False
    raw_len: int = 0
    notes: list[str] = field(default_factory=list)   # "insecure_tls", "no_ua_retry", "pdf_ocr", ...

    # Backwards-compatible tuple view: `status, text = page` still works.
    def __iter__(self):
        yield self.status
        yield self.text


def require_curl() -> None:
    """Raise FetchError with install instructions if curl is missing."""
    if shutil.which("curl") is None:
        raise FetchError(_CURL_INSTALL_HINT)


def download(url: str, out_path: str | Path, *, timeout: int = 60,
             ua: str = CHROME_UA, min_bytes: int | None = None) -> Path:
    """
    curl `url` to `out_path`. Raises FetchError if curl fails or (when
    min_bytes is set) the body is suspiciously small — e.g. a Google Sheet
    that's no longer public, or a CSB error page.
    """
    require_curl()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl", "-sL", "--compressed", "-A", ua, "--max-time", str(timeout),
         url, "-o", str(out_path)],
        capture_output=True, text=True, timeout=timeout + 10,
    )
    if result.returncode != 0:
        raise FetchError(f"curl failed for {url}: {result.stderr.strip()}")
    if min_bytes is not None:
        size = out_path.stat().st_size
        if size < min_bytes:
            raise FetchError(
                f"{url} returned a suspiciously small body ({size} bytes; "
                f"expected >= {min_bytes}) — check the URL is still valid "
                f"and publicly accessible."
            )
    return out_path


# ---------------------------------------------------------------------------
# PDF / text extraction helpers
# ---------------------------------------------------------------------------

def _pdftotext(path: str) -> str:
    """poppler `pdftotext -layout`; '' on any failure."""
    try:
        r = subprocess.run(["pdftotext", "-layout", path, "-"],
                           capture_output=True, timeout=120)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return ""


def _pypdf_text(path: str, max_pages: int = 400) -> str:
    """In-process fallback when pdftotext is missing/empty; '' on failure."""
    try:
        from pypdf import PdfReader
        rd = PdfReader(path)
        parts = []
        for pg in rd.pages[:max_pages]:
            try:
                parts.append(pg.extract_text() or "")
            except Exception:  # noqa: BLE001 — one bad page shouldn't sink the doc
                continue
        return "\n".join(parts)
    except Exception:  # noqa: BLE001
        return ""


def _pdf_ocr(path: str, lang: str = "eng+kor+chi_sim") -> str:
    """OCR a scanned PDF via pdftoppm + tesseract, capped at _OCR_MAX_PAGES.
    '' when either binary is missing or nothing comes out. Only called when
    the text layer is (nearly) empty, since OCR is slow. OCR output mangles
    digits and accents, so prefer long alphabetic tokens when verifying
    against an OCR'd document."""
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return ""
    # Fall back to plain English if the extra language packs aren't installed.
    try:
        langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True,
                               text=True, timeout=30).stdout.split()
        lang = "+".join(l for l in lang.split("+") if l in langs) or "eng"
    except (FileNotFoundError, subprocess.SubprocessError):
        lang = "eng"
    try:
        with tempfile.TemporaryDirectory(prefix="lngct_ocr_") as tmpdir:
            stem = os.path.join(tmpdir, "pg")
            r = subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png",
                                "-l", str(_OCR_MAX_PAGES), path, stem],
                               capture_output=True, timeout=180)
            if r.returncode != 0:
                return ""
            chunks = []
            for name in sorted(os.listdir(tmpdir)):
                if not name.endswith(".png"):
                    continue
                t = subprocess.run(["tesseract", os.path.join(tmpdir, name), "stdout",
                                    "-l", lang, "--psm", "6"],
                                   capture_output=True, text=True, timeout=120)
                if t.returncode == 0 and t.stdout.strip():
                    chunks.append(t.stdout)
            return "\n".join(chunks)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return ""


def pdf_text(path: str) -> tuple[str, list[str]]:
    """Best-effort text of a PDF on disk: pdftotext -> pypdf -> OCR.
    Returns (text, notes)."""
    notes = []
    text = _pdftotext(path)
    if len(text.strip()) < _PDF_TEXT_MIN:
        alt = _pypdf_text(path)
        if len(alt.strip()) > len(text.strip()):
            text, _ = alt, notes.append("pdf_pypdf")
    if len(text.strip()) < _PDF_TEXT_MIN:
        ocr = _pdf_ocr(path)
        if ocr.strip():
            text, _ = ocr, notes.append("pdf_ocr")
    return text, notes


def _decode_html(raw: bytes, content_type: str) -> str:
    """Decode an HTML body honouring the declared charset (header, then meta),
    widening narrow CJK declarations; utf-8-with-replacement as the last resort."""
    enc = None
    m = re.search(r"charset\s*=\s*[\"']?\s*([A-Za-z0-9_\-]+)", content_type or "", re.I)
    if m:
        enc = m.group(1).lower()
    if not enc or enc in ("iso-8859-1", "ascii", "us-ascii", "latin-1", "latin1"):
        mm = _META_CHARSET_RE.search(raw[:4096])
        if mm:
            enc = mm.group(1).decode("ascii", "ignore").strip().lower()
    if enc:
        enc = _CHARSET_WIDEN.get(enc, enc)
        try:
            codecs.lookup(enc)
            return raw.decode(enc, errors="replace")
        except (LookupError, ValueError):
            pass
    return raw.decode("utf-8", errors="replace")


def _looks_like_pdf(url: str, content_type: str, raw: bytes) -> bool:
    return ("pdf" in (content_type or "").lower()
            or url.split("?")[0].lower().endswith(".pdf")
            or raw[:5] == b"%PDF-")


# ---------------------------------------------------------------------------
# The fetch
# ---------------------------------------------------------------------------

def _curl(url: str, tmp: str, timeout: int, ua: str | None, insecure: bool):
    cmd = ["curl", "-sL", "--compressed", "-o", tmp,
           "-w", "%{http_code}\t%{content_type}\t%{url_effective}",
           "--max-time", str(timeout)]
    if ua:
        cmd += ["-A", ua]
    if insecure:
        cmd += ["-k"]
    return subprocess.run(cmd + [url], capture_output=True, text=True,
                          timeout=timeout + 10)


def fetch_page(url: str, *, timeout: int = 30, ua: str = CHROME_UA) -> Page:
    """
    Fetch `url` and return a Page. HTTP errors are reported in `status`
    ("404", "000" when curl couldn't connect), never raised — callers like the
    §3.8 gate turn them into (False, reason). Only a missing curl binary raises.

    The body lands in a private temp file that is always cleaned up. A fixed
    filename would let concurrent verifier runs (parallel subagents in one
    batch) overwrite each other's download — never reuse a shared path here.
    """
    require_curl()
    fd, tmp = tempfile.mkstemp(prefix="lngct_fetch_", suffix=".bin")
    os.close(fd)
    notes: list[str] = []
    status, content_type, final_url, raw = "000", "", "", b""
    try:
        # attempt 1: browser UA; attempt 2: same but -k after an SSL failure;
        # attempt 3: no UA after a transport failure / empty body.
        attempts = [(ua, False)]
        while attempts:
            cur_ua, insecure = attempts.pop(0)
            try:
                result = _curl(url, tmp, timeout, cur_ua, insecure)
            except subprocess.TimeoutExpired:
                status = "000"
                break
            parts = (result.stdout or "").split("\t")
            status = (parts[0].strip() if parts and parts[0].strip() else "000")
            content_type = parts[1].strip().lower() if len(parts) > 1 else ""
            final_url = parts[2].strip() if len(parts) > 2 else ""
            try:
                raw = Path(tmp).read_bytes()
            except OSError:
                raw = b""
            if result.returncode == 0 and (raw or status not in ("000", "")):
                if insecure:
                    notes.append("insecure_tls")
                if cur_ua is None:
                    notes.append("no_ua_retry")
                break
            err = (result.stderr or "").strip()
            if result.returncode in _CURL_SSL_EXITS and not insecure:
                attempts.append((cur_ua, True))
                continue
            if status in ("000", "") and cur_ua is not None:
                attempts.append((None, insecure))
                continue
            if err:
                # Surface the failure instead of silently treating it as an
                # empty page (the old behavior masked DNS/TLS errors).
                print(f"  [fetch] curl error for {url}: {err}", file=sys.stderr)

        is_pdf = _looks_like_pdf(url, content_type, raw)
        if is_pdf and raw[:5] != b"%PDF-" and raw.lstrip()[:1] == b"<":
            # A .pdf URL that returned HTML is an interstitial (bot challenge,
            # login wall), not a PDF. Hand the HTML downstream so the soft-error
            # / bot-wall checks can see it.
            is_pdf = False
        if is_pdf:
            text, pdf_notes = pdf_text(tmp)
            notes.extend(pdf_notes)
        else:
            text = _decode_html(raw, content_type)
        return Page(status=status, text=text, content_type=content_type,
                    final_url=final_url, is_pdf=is_pdf, raw_len=len(raw), notes=notes)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def fetch_text(url: str, *, timeout: int = 30,
               ua: str = CHROME_UA) -> tuple[str, str]:
    """(http_status, body_text) — the simple form. See fetch_page for the rest."""
    p = fetch_page(url, timeout=timeout, ua=ua)
    return p.status, p.text


def page_title(body: str) -> str:
    """Extract the <title> text of an HTML body ("" if none)."""
    m = re.search(r"<title[^>]*>([^<]+)</title>", body, re.IGNORECASE)
    return m.group(1).strip() if m else ""

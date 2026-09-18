"""Get the inputs onto disk: fetch the video and the manual, render the manual to images."""

import ipaddress
import shutil
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pymupdf

USER_AGENT = "compliance-inspector/1.0"
MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB ceiling, so a bad URL cannot fill the disk


def check_public_url(url: str) -> None:
    """Reject URLs that would make the server fetch from itself or its private network.

    Without this, a user-supplied URL could read the NIM at localhost:8000, other services
    on the host, or cloud instance metadata (169.254.169.254).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are accepted")
    if not parsed.hostname:
        raise ValueError("URL has no host")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host {parsed.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(f"URL points at a non-public address ({ip})")


def download(url: str, dest, *, allow_local: bool = False) -> Path:
    """Stream a URL to `dest`.

    `allow_local` lets trusted server-side callers (the preloaded products) copy local
    files. It must stay False for anything a user typed.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    parsed = urlparse(url)
    if allow_local and parsed.scheme in ("", "file"):
        src = Path(parsed.path if parsed.scheme == "file" else url)
        if not src.exists():
            raise FileNotFoundError(f"No such file: {src}")
        shutil.copy(src, dest)
        return dest

    check_public_url(url)

    written = 0
    # Redirects are not followed automatically: each hop is re-checked, so a public URL
    # cannot bounce the request to a private address.
    for _ in range(5):
        with httpx.stream("GET", url, follow_redirects=False, timeout=120,
                          headers={"User-Agent": USER_AGENT}) as resp:
            if resp.is_redirect:
                url = str(resp.url.join(resp.headers["location"]))
                check_public_url(url)
                continue
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for block in resp.iter_bytes(1 << 20):
                    written += len(block)
                    if written > MAX_BYTES:
                        raise ValueError(f"Download exceeded {MAX_BYTES} bytes")
                    fh.write(block)
            return dest
    raise ValueError("Too many redirects")


def render_pdf_pages(pdf_path, pages_dir, dpi: int = 150) -> list[Path]:
    """One PNG per manual page. Cached: existing pages are left alone."""
    pages_dir = Path(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    out = []
    doc = pymupdf.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            target = pages_dir / f"page_{i + 1:02d}.png"
            if not target.exists():
                page.get_pixmap(dpi=dpi).save(target)
            out.append(target)
    finally:
        doc.close()
    return out

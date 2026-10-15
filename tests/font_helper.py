
"""Dev/test helper: find a system font with Arabic glyphs (never bundled with the app)."""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

# (regular, bold) file names; the first font that really covers Arabic wins.
CANDIDATES = (
    ("simpo.ttf", "simpbdo.ttf"),      # Simplified Arabic
    ("trado.ttf", "tradbdo.ttf"),      # Traditional Arabic
    ("arial.ttf", "arialbd.ttf"),
    ("tahoma.ttf", "tahomabd.ttf"),
    ("segoeui.ttf", "segoeuib.ttf"),
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
)

_LETTERS = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"


def _needed_codepoints() -> set[int]:
    """Every code point the reshaper can emit for common Arabic text, plus digits/punctuation."""
    import arabic_reshaper
    samples = [_LETTERS, "لا لأ لإ لآ", "١٢٣٤٥٦٧٨٩٠ ، ؟"]
    for ch in _LETTERS:
        samples += [ch, "ب" + ch, ch + "ب", "ب" + ch + "ب"]  # isolated/final/initial/medial
    shaped = "".join(arabic_reshaper.reshape(s) for s in samples)
    return {ord(c) for c in shaped if not c.isspace()} | {ord(c) for c in _LETTERS}


def missing_codepoints(path: Path) -> list[int]:
    """Code points the font cannot draw (needs arabic-reshaper installed)."""
    from reportlab.pdfbase.ttfonts import TTFontFile
    cmap = TTFontFile(str(path)).charToGlyph
    return sorted(_needed_codepoints() - set(cmap))


def has_arabic_glyphs(path: Path) -> bool:
    """True only when the font covers all shaped forms (False if unreadable)."""
    try:
        return not missing_codepoints(path)
    except ImportError:  # arabic-reshaper missing: the PDF export would fail anyway
        return False
    except Exception:  # noqa: BLE001 - unreadable font file
        return False


def _font_files() -> dict[str, Path]:
    """Lower-case file name -> path, from the Windows font folders (and Linux DejaVu)."""
    dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
    if local := os.environ.get("LOCALAPPDATA"):
        dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    dirs.append(Path("/usr/share/fonts/truetype/dejavu"))
    return {p.name.lower(): p for d in dirs if d.is_dir() for p in d.iterdir()
            if p.suffix.lower() == ".ttf"}




def prepare_font_dir() -> tuple[Path, str] | None:
    """Copy a suitable system font into a temp dir under a name the app looks for.

    Returns (font_dir, description) or None when no system font qualifies.
    """
    files = _font_files()
    for regular, bold in CANDIDATES:
        path = files.get(regular.lower())
        if path is None or not has_arabic_glyphs(path):
            continue
        tmp = Path(tempfile.mkdtemp(prefix="dbfonts_"))
        atexit.register(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(path, tmp / "DejaVuSans.ttf")  # ARABIC_FONT_FILES fallback name
        if (bold_path := files.get(bold.lower())) is not None:
            shutil.copy(bold_path, tmp / "DejaVuSans-Bold.ttf")
        return tmp, f"system font {path.name} (check only, do not ship it)"
    return None

if __name__ == "__main__":
    # Diagnostic: python -m tests.font_helper
    files = _font_files()
    for regular, _bold in CANDIDATES:
        path = files.get(regular.lower())
        if path is None:
            print(f"{regular:18} not installed")
            continue
        try:
            gaps = missing_codepoints(path)
        except Exception as exc:  # noqa: BLE001
            print(f"{regular:18} error: {exc}")
            continue
        print(f"{regular:18} " + ("OK" if not gaps else
              f"missing {len(gaps)}: " + " ".join(f"U+{c:04X}" for c in gaps[:20])))

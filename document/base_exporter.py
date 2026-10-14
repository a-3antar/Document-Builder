"""Template-method base: type check, atomic write, verification, timing."""
from __future__ import annotations

import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.exceptions import (DocumentBuilderError, ExportError, ExportValidationError,
                             UnsupportedContentError)
from core.interfaces import BaseExporter, ExportResult

log = logging.getLogger(__name__)


class FileExporter(BaseExporter, ABC):
    """Subclasses implement _write and _verify; this class guarantees atomic output."""

    extension: str = ""
    content_type: type = object
    features: frozenset[str] = frozenset()

    def supports(self, feature: str) -> bool:
        return feature in self.features

    @abstractmethod
    def _write(self, content: Any, path: Path, warnings: list[str]) -> None:
        """Write the file to `path` (a temp file) and append non-fatal notes to warnings."""

    @abstractmethod
    def _verify(self, path: Path) -> None:
        """Re-open the file with its library; raise on any problem."""

    def export(self, content: Any, output_path: Path) -> ExportResult:
        if not isinstance(content, self.content_type):
            raise UnsupportedContentError(
                f"{type(self).__name__} cannot export {type(content).__name__}.")
        out = Path(output_path)
        if out.suffix.lower() != self.extension:
            raise ExportError(f"Output file must end with '{self.extension}'.")
        if not out.parent.is_dir():
            raise ExportError(f"Output folder does not exist: {out.parent}",
                              hint="Choose an existing folder.")
        start, warnings = time.perf_counter(), []
        fd, tmp_name = tempfile.mkstemp(dir=out.parent, prefix=f".{out.stem}.",
                                        suffix=f".tmp{self.extension}")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            self._write(content, tmp, warnings)
            self._check(tmp)
            os.replace(tmp, out)
        except DocumentBuilderError:
            raise
        except PermissionError as exc:
            raise ExportError(f"Cannot write '{out.name}': access denied.",
                              hint="Close the file if it is open in another program.") from exc
        except OSError as exc:
            raise ExportError(f"Cannot write '{out.name}': {exc.strerror or exc}",
                              hint="Check free disk space and folder permissions.") from exc
        except Exception as exc:  # noqa: BLE001 - library failures vary
            raise ExportError(f"Failed to create the {self.extension} file: {exc}") from exc
        finally:
            tmp.unlink(missing_ok=True)
        size, took = out.stat().st_size, time.perf_counter() - start
        log.info("Exported %s (%d bytes) in %.2fs", out.name, size, took)
        return ExportResult(out, size, took, tuple(warnings))

    def _check(self, tmp: Path) -> None:
        if not tmp.is_file() or tmp.stat().st_size == 0:
            raise ExportValidationError("The generated file is empty.")
        try:
            self._verify(tmp)
        except Exception as exc:  # noqa: BLE001
            raise ExportValidationError(f"The generated file failed validation: {exc}") from exc

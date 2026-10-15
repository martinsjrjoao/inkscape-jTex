#!/usr/bin/env python3
"""
jTeX - Inkscape 1.x extension

Compiles a piece of LaTeX code using `latex` + `dvisvgm` (the same backend
TexText uses by default) and inserts the result into the current document
as a group of fully editable vector paths. It depends on neither installed
fonts nor an internet connection.

The original LaTeX source is stored in `data-latex-*` attributes on the
created group, for future reference.
"""

import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

import inkex
from inkex import Group
from lxml import etree

# Inkscape uses 96 px per inch; LaTeX/dvisvgm output is in pt (72 per inch).
UNIT_TO_PX = {
    "pt": 96.0 / 72.0,
    "px": 1.0,
    "mm": 96.0 / 25.4,
    "cm": 96.0 / 2.54,
    "in": 96.0,
}

SVG_NS = "http://www.w3.org/2000/svg"

# Base font size is fixed; use the "scale" option to resize the result.
FONT_SIZE = 10

# Allowed LaTeX font declarations (the .inx offers a subset of these).
FAMILIES = {"rmfamily", "sffamily", "ttfamily"}
STYLES = {"bfseries", "itshape", "slshape", "scshape", "mdseries", "upshape"}



class LatexFormula(inkex.EffectExtension):

    def add_arguments(self, pars):
        pars.add_argument("--latex_code", type=str, default="x^2 + y^2 = z^2")
        pars.add_argument("--preamble", type=str, default="")
        pars.add_argument("--mode", type=str, default="equation")
        pars.add_argument("--family", type=str, default="rmfamily")
        pars.add_argument("--style", type=str, default="")
        pars.add_argument("--scale", type=float, default=1.0)

    def effect(self):
        macos_path = "/Library/TeX/texbin"
        if os.path.exists(macos_path) and macos_path not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + macos_path

        code = (self.options.latex_code or "").strip()
        preamble = self.options.preamble or ""
        mathmode = self.options.mode != "text"
        user_scale = self.options.scale

        if not code:
            raise inkex.AbortExtension("No LaTeX code was provided.")

        latex_bin = shutil.which("latex")
        dvisvgm_bin = shutil.which("dvisvgm")

        if latex_bin is None:
            raise inkex.AbortExtension(
                "The 'latex' executable was not found in the system PATH.\n"
                "Check that TeX Live / MiKTeX / MacTeX is installed "
                "and reachable from Inkscape."
            )
        if dvisvgm_bin is None:
            raise inkex.AbortExtension(
                "The 'dvisvgm' executable was not found in the system PATH.\n"
                "It normally ships with TeX Live / MiKTeX / MacTeX; "
                "check your installation."
            )

        # Equation mode wraps the code in display math; text mode inserts it as-is.
        content = f"\\[ {code} \\]" if mathmode else code

        # Font family / style declarations (see Overleaf's "Font sizes,
        # families, and styles"). Only whitelisted values reach the LaTeX source.
        decls = ""
        if self.options.family in FAMILIES:
            decls += "\\" + self.options.family + " "
        for style in self.options.style.split():
            if style in STYLES:
                decls += "\\" + style + " "
        if decls:
            content = "{" + decls + content + "}"

        tex_source = (
            f"\\documentclass[{FONT_SIZE}pt,preview,border=2pt]{{standalone}}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{amssymb}\n"
            "\\usepackage{siunitx}\n"
            "\\usepackage{altsubsup}\n"
            f"{preamble}\n"
            "\\begin{document}\n"
            f"{content}\n"
            "\\end{document}\n"
        )

        with tempfile.TemporaryDirectory(prefix="inkscape_latex_") as tmpdir:
            tex_path = os.path.join(tmpdir, "document.tex")
            with open(tex_path, "w", encoding="utf-8") as fh:
                fh.write(tex_source)

            proc = subprocess.run(
                [
                    latex_bin,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory", tmpdir,
                    tex_path,
                ],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                raise inkex.AbortExtension(
                    "Failed to compile LaTeX:\n\n"
                    + self._extract_latex_error(os.path.join(tmpdir, "document.log"))
                )

            dvi_path = os.path.join(tmpdir, "document.dvi")
            svg_path = os.path.join(tmpdir, "out.svg")

            proc = subprocess.run(
                [dvisvgm_bin, "--no-fonts", "--output=" + svg_path, dvi_path],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0 or not os.path.exists(svg_path):
                raise inkex.AbortExtension(
                    "Failed to convert to SVG (dvisvgm):\n\n"
                    + (proc.stderr or "")[-2000:]
                )

            self._insert_svg(svg_path, code, preamble, mathmode, user_scale)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_latex_error(log_path):
        if not os.path.exists(log_path):
            return "Could not read the LaTeX log."
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
            log = fh.read()
        errors = re.findall(r"^! .*(?:\n.*){0,4}", log, re.MULTILINE)
        if errors:
            return "\n\n".join(errors[:3])
        return log[-1500:]

    @staticmethod
    def _make_ids_unique(root):
        """dvisvgm names glyphs like "g0-97" in every run, so ids from
        different insertions would collide in the document's <defs> (the
        first definition wins, e.g. an italic math "a" replacing a text "a").
        Prefix every id, and every reference to it, with a unique token."""
        prefix = "jtex" + uuid.uuid4().hex[:8] + "-"
        ids = {el.get("id") for el in root.iter() if el.get("id")}
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            if el.get("id"):
                el.set("id", prefix + el.get("id"))
            for attr, val in list(el.attrib.items()):
                if attr.endswith("href") and val.startswith("#") and val[1:] in ids:
                    el.set(attr, "#" + prefix + val[1:])
                elif "url(#" in val:
                    el.set(attr, re.sub(
                        r"url\(#([^)]+)\)",
                        lambda m: "url(#%s%s)" % (prefix, m.group(1)) if m.group(1) in ids else m.group(0),
                        val))

    @staticmethod
    def _split_unit(value):
        match = re.match(r"([\d.]+)\s*([a-zA-Z%]*)", (value or "").strip())
        if not match:
            return 0.0, "pt"
        num, unit = match.groups()
        return float(num), (unit or "pt")

    def _insert_svg(self, svg_path, code, preamble, mathmode, user_scale):
        tree = etree.parse(svg_path)
        src_root = tree.getroot()
        self._make_ids_unique(src_root)

        width, w_unit = self._split_unit(src_root.get("width", "0pt"))
        vb = src_root.get("viewBox")
        if vb:
            vb_x, vb_y, vb_w, vb_h = (float(v) for v in vb.split())
        else:
            vb_x = vb_y = 0.0
            vb_w = width
            vb_h, _ = self._split_unit(src_root.get("height", "0pt"))

        # Convert "1 <dvisvgm unit>" to user units of THIS document. This is
        # essential: if the document has a non-default page scale
        # (1 user unit != 1/96in), a fixed 96/72 factor would be wrong.
        # unittouu knows the document's real scale.
        try:
            px_per_unit = self.svg.unittouu(f"1{w_unit}")
        except Exception:
            px_per_unit = UNIT_TO_PX.get(w_unit, UNIT_TO_PX["pt"])
        final_scale = px_per_unit * user_scale
        final_w = vb_w * final_scale
        final_h = vb_h * final_scale

        layer = self.svg.get_current_layer()
        group = layer.add(Group())
        group.set("inkscape:label", "LaTeX: " + code[:60])

        # Keep the original code for reference / future manual editing.
        group.set("data-latex-code", base64.b64encode(code.encode("utf-8")).decode("ascii"))
        group.set("data-latex-preamble", base64.b64encode(preamble.encode("utf-8")).decode("ascii"))
        group.set("data-latex-mathmode", "1" if mathmode else "0")

        # Move the generated SVG's defs into the current document's defs.
        defs_src = src_root.find(f"{{{SVG_NS}}}defs")
        if defs_src is not None:
            doc_defs = self.svg.defs
            for child in list(defs_src):
                doc_defs.append(child)

        # Move the visible content (groups/paths/use) into the new group.
        for child in list(src_root):
            if not isinstance(child.tag, str):
                continue  # skip comments / processing instructions
            if etree.QName(child).localname == "defs":
                continue
            group.append(child)

        # Insertion point: the center of the visible area (what the user
        # sees on screen); if the API is missing in this inkex version, fall
        # back to the page center. Both return the document's own user units,
        # so they work regardless of page unit/size.
        cx, cy = self._document_center()

        insert_x = cx - final_w / 2.0
        insert_y = cy - final_h / 2.0

        group.transform = (
            inkex.Transform(f"translate({insert_x},{insert_y})")
            @ inkex.Transform(f"scale({final_scale})")
            @ inkex.Transform(f"translate({-vb_x},{-vb_y})")
        )

    def _document_center(self):
        """Return (cx, cy) in document user units: the center of the current
        view if available, otherwise the page center (via viewBox)."""
        # 1) Center of the current view (zoom/pan) - highest-level API.
        try:
            center = self.svg.namedview.center
            return float(center.x), float(center.y)
        except Exception:
            pass

        # 2) Page center straight from the viewBox - already in user units.
        try:
            vb = self.svg.get_viewbox()
            if vb:
                return vb[0] + vb[2] / 2.0, vb[1] + vb[3] / 2.0
        except Exception:
            pass

        # 3) Last resort.
        try:
            return float(self.svg.viewbox_width) / 2.0, float(self.svg.viewbox_height) / 2.0
        except Exception:
            return 0.0, 0.0


if __name__ == "__main__":
    LatexFormula().run()
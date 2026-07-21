#!/usr/bin/env python3
"""
jTeX - extensão para Inkscape 1.x

Compila um trecho de código LaTeX usando `latex` + `dvisvgm` (o mesmo
backend usado por padrão pelo TexText) e insere o resultado no documento
atual como um grupo de caminhos (paths) vetoriais totalmente editáveis
— não depende de fontes instaladas nem de conexão externa.

O código-fonte LaTeX original fica guardado em atributos `data-latex-*`
no grupo criado, para referência futura.
"""

import base64
import os
import re
import shutil
import subprocess
import tempfile

import inkex
from inkex import Group
from lxml import etree

# Inkscape usa 96 px por polegada; o LaTeX/dvisvgm produz saída em pt (72/pol).
UNIT_TO_PX = {
    "pt": 96.0 / 72.0,
    "px": 1.0,
    "mm": 96.0 / 25.4,
    "cm": 96.0 / 2.54,
    "in": 96.0,
}

SVG_NS = "http://www.w3.org/2000/svg"


class LatexFormula(inkex.EffectExtension):

    def add_arguments(self, pars):
        pars.add_argument("--latex_code", type=str, default="x^2 + y^2 = z^2")
        pars.add_argument("--preamble", type=str, default="")
        pars.add_argument("--mathmode", type=inkex.Boolean, default=True)
        pars.add_argument("--fontsize", type=str, default="12")
        pars.add_argument("--scale", type=float, default=1.0)

    def effect(self):
        macos_path = "/Library/TeX/texbin"
        if os.path.exists(macos_path) and macos_path not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + macos_path

        code = (self.options.latex_code or "").strip()
        preamble = self.options.preamble or ""
        mathmode = self.options.mathmode
        fontsize = self.options.fontsize
        user_scale = self.options.scale

        if not code:
            raise inkex.AbortExtension("Nenhum código LaTeX foi informado.")

        latex_bin = shutil.which("latex")
        dvisvgm_bin = shutil.which("dvisvgm")

        if latex_bin is None:
            raise inkex.AbortExtension(
                "O executável 'latex' não foi encontrado no PATH do sistema.\n"
                "Verifique se o TeX Live / MiKTeX / MacTeX está instalado "
                "e acessível a partir do Inkscape."
            )
        if dvisvgm_bin is None:
            raise inkex.AbortExtension(
                "O executável 'dvisvgm' não foi encontrado no PATH do sistema.\n"
                "Ele normalmente já vem junto com o TeX Live / MiKTeX / MacTeX; "
                "verifique sua instalação."
            )

        content = f"\\[ {code} \\]" if mathmode else code

        tex_source = (
            f"\\documentclass[{fontsize}pt,preview,border=2pt]{{standalone}}\n"
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

            self._insert_svg(svg_path, code, preamble, mathmode, fontsize, user_scale)

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_latex_error(log_path):
        if not os.path.exists(log_path):
            return "It was not possible to read the log of the LaTeX."
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
            log = fh.read()
        errors = re.findall(r"^! .*(?:\n.*){0,4}", log, re.MULTILINE)
        if errors:
            return "\n\n".join(errors[:3])
        return log[-1500:]

    @staticmethod
    def _split_unit(value):
        match = re.match(r"([\d.]+)\s*([a-zA-Z%]*)", (value or "").strip())
        if not match:
            return 0.0, "pt"
        num, unit = match.groups()
        return float(num), (unit or "pt")

    def _insert_svg(self, svg_path, code, preamble, mathmode, fontsize, user_scale):
        tree = etree.parse(svg_path)
        src_root = tree.getroot()

        width, w_unit = self._split_unit(src_root.get("width", "0pt"))
        vb = src_root.get("viewBox")
        if vb:
            vb_x, vb_y, vb_w, vb_h = (float(v) for v in vb.split())
        else:
            vb_x = vb_y = 0.0
            vb_w = width
            vb_h, _ = self._split_unit(src_root.get("height", "0pt"))

        # Converte "1 <unidade do dvisvgm>" para user units DESTE documento.
        # Isso é essencial: se o documento tem uma escala de página
        # diferente do padrão (1 user unit = 1/96in), um fator fixo
        # 96/72 fica errado. unittouu já sabe a escala real do documento.
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

        # Guarda o código original para referência / futura edição manual.
        group.set("data-latex-code", base64.b64encode(code.encode("utf-8")).decode("ascii"))
        group.set("data-latex-preamble", base64.b64encode(preamble.encode("utf-8")).decode("ascii"))
        group.set("data-latex-mathmode", "1" if mathmode else "0")
        group.set("data-latex-fontsize", str(fontsize))

        # Move definições (defs) do SVG gerado para o defs do documento atual.
        defs_src = src_root.find(f"{{{SVG_NS}}}defs")
        if defs_src is not None:
            doc_defs = self.svg.defs
            for child in list(defs_src):
                doc_defs.append(child)

        # Move o conteúdo visível (grupos/paths/use) para dentro do novo grupo.
        for child in list(src_root):
            if not isinstance(child.tag, str):
                continue  # ignora comentários / instruções de processamento
            if etree.QName(child).localname == "defs":
                continue
            group.append(child)

        # Centro de inserção: tenta o centro da área visível (o que o
        # usuário está vendo na tela); se a API não existir nesta versão
        # do inkex, cai para o centro geométrico da página. Ambas as
        # fontes já retornam valores em "user units" do próprio documento,
        # então funcionam independente da unidade/tamanho de página.
        cx, cy = self._document_center()

        insert_x = cx - final_w / 2.0
        insert_y = cy - final_h / 2.0

        group.transform = (
            inkex.Transform(f"translate({insert_x},{insert_y})")
            @ inkex.Transform(f"scale({final_scale})")
            @ inkex.Transform(f"translate({-vb_x},{-vb_y})")
        )

    def _document_center(self):
        """Retorna (cx, cy) em user units do documento, tentando primeiro
        o centro da área visível atual e, se não for possível, o centro
        geométrico da página (via viewBox)."""
        # 1) Centro da visão atual (zoom/pan) — API de mais alto nível.
        try:
            center = self.svg.namedview.center
            return float(center.x), float(center.y)
        except Exception:
            pass

        # 2) Centro geométrico da página, direto do viewBox — já em user
        #    units, então é seguro para qualquer unidade/tamanho de página.
        try:
            vb = self.svg.get_viewbox()
            if vb:
                return vb[0] + vb[2] / 2.0, vb[1] + vb[3] / 2.0
        except Exception:
            pass

        # 3) Último recurso.
        try:
            return float(self.svg.viewbox_width) / 2.0, float(self.svg.viewbox_height) / 2.0
        except Exception:
            return 0.0, 0.0


if __name__ == "__main__":
    LatexFormula().run()
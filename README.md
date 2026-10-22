# jTeX — LaTeX for Inkscape

Inserts LaTeX text or equations into Inkscape (1.0 or newer, tested on 1.4+)
as a group of fully editable vector paths, with no dependency on installed
fonts. It uses the same backend TexText uses by default:
`latex` → `.dvi` → `dvisvgm` → SVG.

Since `dvisvgm` converts glyphs to *paths*, the result can be edited like any
other vector drawing (Edit nodes, Ungroup, etc.).

## Features

- **Equation** mode wraps your code in `\[ ... \]`; **Text** mode inserts it
  as-is, so you can write plain text (`Hello \textbf{world}`) or take full
  control of the math mode yourself (`align`, `$...$`, etc.).
- **Font family** (Roman, Sans serif, Monospace) and **Font style** (Normal,
  Bold, Italic, Slanted, Small caps, Bold italic) via LaTeX's
  `\rmfamily`/`\sffamily`/`\ttfamily` and `\bfseries`/`\itshape`/`\slshape`/
  `\scshape`. In Equation mode they affect text inside the formula (e.g.
  `\text{...}`); math symbols keep their math fonts unless you use
  `\mathsf`, `\mathbf`, etc. yourself.
- Base font size is always 10 pt; use **Scale** to resize.
- Extra LaTeX packages can be added in the preamble field.

## Requirements

- LaTeX in the system PATH (`latex`).
- `dvisvgm` in the PATH (normally bundled with TeX Live / MiKTeX / MacTeX;
  otherwise `tlmgr install dvisvgm`).
- LaTeX packages `standalone`, `preview`, `amsmath`, `amssymb`, `siunitx`,
  `altsubsup` (included in a full TeX Live / MiKTeX / MacTeX install).

With a minimal install (e.g. BasicTeX on macOS) some of these are missing;
install them with:

```
sudo tlmgr install dvisvgm standalone preview siunitx altsubsup
```

On macOS the extension automatically adds `/Library/TeX/texbin` to the PATH,
so MacTeX/BasicTeX work even when Inkscape is launched from the Finder. Tools
installed elsewhere (e.g. Homebrew in `/opt/homebrew/bin`) are not found
unless Inkscape is started from a terminal that has them in its PATH.

Quick check in a terminal:

```
latex --version
dvisvgm --version
```

## Installation

Copy the whole `jtex` folder (it contains `latex_formula.inx`,
`latex_formula.py` and `spacer.png`) into the Inkscape user extensions folder,
so you end up with e.g. `.../extensions/jtex/latex_formula.inx`:

- **Linux**: `~/.config/inkscape/extensions/`
  (Flatpak: `~/.var/app/org.inkscape.Inkscape/config/inkscape/extensions/`;
  note that the Flatpak sandbox cannot see the system's `latex`, so prefer the
  regular package or AppImage)
- **macOS**: `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
- **Windows**: `%APPDATA%\Inkscape\extensions\`

If unsure about the exact path, open Inkscape and go to
**Edit → Preferences → System**; the "User extensions" field shows it and has
a button to open the folder.

Restart Inkscape after copying the files.

## Usage

1. Go to **Extensions → Text → jTeX...**
2. Pick the mode (**Equation** or **Text**) and type your LaTeX code
   (e.g. `x^2 + y^2 = z^2`, `\frac{a}{b}`, or `Some \textbf{bold} text`).
3. Set the **Scale** if needed.
4. Add extra packages in the preamble field if needed, e.g.
   `\usepackage{mathtools}` or `\usepackage{xcolor}`, one per line.
5. Click **Apply**. The result is inserted centered in the current view as a
   group of paths.

### TikZ / pgfplots

TikZ and pgfplots work in **Text** mode (not Equation, which wraps the code in
`\[ ... \]`). Because the pipeline goes through DVI, TikZ needs the
`dvisvgm` driver, which must be selected *before* TikZ is loaded. Put this in
the **Extra packages** field:

```
\def\pgfsysdriver{pgfsys-dvisvgm.def}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=newest}
```

Then paste the whole `tikzpicture` (including `\begin{tikzpicture}` and
`\end{tikzpicture}`) in the **LaTeX code** field:

```
\begin{tikzpicture}
  \begin{axis}[axis lines=middle, xlabel={$x$}, ylabel={$y$}]
    \addplot[blue, thick] {x^2};
  \end{axis}
\end{tikzpicture}
```

Notes:

- `pgfplots` already loads `tikz`; for plain TikZ drawings (no `axis`) you can
  load only `tikz`, but the driver line is still required.
- `dvisvgm` may print "PostScript specials ignored"; the result is still
  correct.
- Without the driver line, parts of the drawing can be missing from the SVG.

## Known limitations

- **No in-place editing**: unlike TexText, this extension cannot reopen an
  inserted object to edit its source. The original LaTeX code is stored in
  custom attributes (`data-latex-code`, Base64) on the created group, for
  reference only. To change a formula, insert it again and replace the old
  object.
- LaTeX compilation errors are shown in an Inkscape dialog with the relevant
  part of the log; missing-package errors appear the same way.
- Large or complex formulas may take a few seconds, since each Apply runs
  `latex` and `dvisvgm` from scratch.

## Why this works when TexText fails

TexText relies on its own GUI integration (GTK) on top of the LaTeX pipeline.
This extension avoids that extra layer: it uses only the standard Inkscape
extension parameters (`.inx`) and calls `latex`/`dvisvgm` directly through
`subprocess`, so there are far fewer failure points related to graphics
libraries, GTK versions, etc.

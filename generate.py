#!/usr/bin/env python3
"""Generate Low Gravitas Zen themes from palette.toml.

Usage:
    python3 generate.py                     # Generate all themes, both variants
    python3 generate.py --variant dark      # Dark only
    python3 generate.py --editor vscode     # VS Code only
    python3 generate.py --check             # Verify generated files match committed
    python3 generate.py --seed-light        # Print HSLuv-inverted light palette candidates
    python3 generate.py --bootstrap         # Extract theme data from existing files (dev tool)
    python3 generate.py --site              # Generate demo site at docs/index.html
"""

import argparse
import json
import math
import os
import sys
import textwrap
import tomllib
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parent
PALETTE_PATH = REPO / "palette.toml"
GENERATED_HEADER_HASH = "# GENERATED — edit palette.toml, then run: python3 generate.py"
GENERATED_HEADER_XML = "<!-- GENERATED — edit palette.toml, then run: python3 generate.py -->"


# ── Color utilities ──────────────────────────────────────────────────────────

def hex_to_rgb(h):
    """'#rrggbb' → (r, g, b) as floats in [0, 1]."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """(r, g, b) floats → '#rrggbb'."""
    return f"#{int(round(r*255)):02x}{int(round(g*255)):02x}{int(round(b*255)):02x}"


def hex_upper(h):
    """'#rrggbb' → 'RRGGBB' (no hash, uppercase — for IntelliJ XML)."""
    return h.lstrip("#").upper()


def hex_with_alpha(h, alpha):
    """'#rrggbb' + 'aa' → '#rrggbbaa'."""
    return f"{h}{alpha}"


# ── HSLuv conversion (for --seed-light) ──────────────────────────────────────

def _rgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _linear_to_rgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1/2.4) - 0.055

def rgb_to_xyz(r, g, b):
    r, g, b = _rgb_to_linear(r), _rgb_to_linear(g), _rgb_to_linear(b)
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    return x, y, z

def xyz_to_rgb(x, y, z):
    r =  3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b =  0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    r = max(0, min(1, _linear_to_rgb(r)))
    g = max(0, min(1, _linear_to_rgb(g)))
    b = max(0, min(1, _linear_to_rgb(b)))
    return r, g, b

_REF_WHITE = (0.95047, 1.0, 1.08883)
_EPSILON = 0.008856
_KAPPA = 903.3

def xyz_to_lab(x, y, z):
    xr, yr, zr = x / _REF_WHITE[0], y / _REF_WHITE[1], z / _REF_WHITE[2]
    fx = xr ** (1/3) if xr > _EPSILON else (_KAPPA * xr + 16) / 116
    fy = yr ** (1/3) if yr > _EPSILON else (_KAPPA * yr + 16) / 116
    fz = zr ** (1/3) if zr > _EPSILON else (_KAPPA * zr + 16) / 116
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return L, a, b

def lab_to_xyz(L, a, b):
    fy = (L + 16) / 116
    fx = a / 500 + fy
    fz = fy - b / 200
    xr = fx**3 if fx**3 > _EPSILON else (116 * fx - 16) / _KAPPA
    yr = fy**3 if L > _KAPPA * _EPSILON else L / _KAPPA
    zr = fz**3 if fz**3 > _EPSILON else (116 * fz - 16) / _KAPPA
    return xr * _REF_WHITE[0], yr * _REF_WHITE[1], zr * _REF_WHITE[2]

def lab_to_lch(L, a, b):
    C = math.sqrt(a*a + b*b)
    H = math.degrees(math.atan2(b, a)) % 360
    return L, C, H

def lch_to_lab(L, C, H):
    a = C * math.cos(math.radians(H))
    b = C * math.sin(math.radians(H))
    return L, a, b

def hex_to_lch(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    x, y, z = rgb_to_xyz(r, g, b)
    L, a, b_val = xyz_to_lab(x, y, z)
    return lab_to_lch(L, a, b_val)

def lch_to_hex(L, C, H):
    La, a, b = lch_to_lab(L, C, H)
    x, y, z = lab_to_xyz(La, a, b)
    r, g, b = xyz_to_rgb(x, y, z)
    return rgb_to_hex(r, g, b)


# ── Palette loading ──────────────────────────────────────────────────────────

def load_palette(variant="dark"):
    """Load palette.toml, applying variant overrides."""
    with open(PALETTE_PATH, "rb") as f:
        data = tomllib.load(f)
    pal = dict(data["base"])
    if variant in data.get("variants", {}):
        pal.update(data["variants"][variant])
    pal["_meta"] = data["meta"]
    return pal


def build_color_map(palette):
    """Build reverse map: lowercase hex → palette key name."""
    cmap = {}
    for k, v in palette.items():
        if k.startswith("_"):
            continue
        if isinstance(v, str) and v.startswith("#"):
            cmap[v.lower()] = k
    return cmap


# ══════════════════════════════════════════════════════════════════════════════
# VS Code theme data
# ══════════════════════════════════════════════════════════════════════════════

# Semantic token colors: key → palette_key
VSCODE_SEMANTIC_TOKENS = OrderedDict([
    ("enumMember", "bright_cyan"),
    ("variable.constant", "bright_yellow"),
    ("variable.defaultLibrary", "yellow"),
])

# Token colors: (name, scope, palette_key_or_None, font_style_or_None)
# scope is either a string or a list of strings
# When palette_key is None, only fontStyle is set (no foreground)
VSCODE_TOKEN_COLORS = [
    ("unison punctuation", "punctuation.definition.delayed.unison,punctuation.definition.list.begin.unison,punctuation.definition.list.end.unison,punctuation.definition.ability.begin.unison,punctuation.definition.ability.end.unison,punctuation.operator.assignment.as.unison,punctuation.separator.pipe.unison,punctuation.separator.delimiter.unison,punctuation.definition.hash.unison", "bright_magenta", None),
    ("haskell variable generic-type", "variable.other.generic-type.haskell", "bright_red", None),
    ("haskell storage type", "storage.type.haskell", "bright_yellow", None),
    ("support.variable.magic.python", "support.variable.magic.python", "bright_magenta", None),
    ("punctuation.separator.parameters.python", "punctuation.separator.period.python,punctuation.separator.element.python,punctuation.parenthesis.begin.python,punctuation.parenthesis.end.python", "white", None),
    ("variable.parameter.function.language.special.self.python", "variable.parameter.function.language.special.self.python", "yellow", None),
    ("storage.modifier.lifetime.rust", "storage.modifier.lifetime.rust", "white", None),
    ("support.function.std.rust", "support.function.std.rust", "bright_blue", None),
    ("entity.name.lifetime.rust", "entity.name.lifetime.rust", "yellow", None),
    ("variable.language.rust", "variable.language.rust", "bright_magenta", None),
    ("support.constant.edge", "support.constant.edge", "bright_red", None),
    ("regexp constant character-class", "constant.other.character-class.regexp", "bright_magenta", None),
    ("regexp operator.quantifier", "keyword.operator.quantifier.regexp", "bright_yellow", None),
    ("punctuation.definition", "punctuation.definition.string.begin,punctuation.definition.string.end", "green", None),
    ("Text", "variable.parameter.function", "white", None),
    ("Comment Markup Link", "comment markup.link", "blue", None),
    ("markup diff", "markup.changed.diff", "yellow", None),
    ("diff", "meta.diff.header.from-file,meta.diff.header.to-file,punctuation.definition.from-file.diff,punctuation.definition.to-file.diff", "bright_blue", None),
    ("inserted.diff", "markup.inserted.diff", "green", None),
    ("deleted.diff", "markup.deleted.diff", "bright_magenta", None),
    ("c++ function", "meta.function.c,meta.function.cpp", "bright_magenta", None),
    ("c++ block", "punctuation.section.block.begin.bracket.curly.cpp,punctuation.section.block.end.bracket.curly.cpp,punctuation.terminator.statement.c,punctuation.section.block.begin.bracket.curly.c,punctuation.section.block.end.bracket.curly.c,punctuation.section.parens.begin.bracket.round.c,punctuation.section.parens.end.bracket.round.c,punctuation.section.parameters.begin.bracket.round.c,punctuation.section.parameters.end.bracket.round.c", "white", None),
    ("js/ts punctuation separator key-value", "punctuation.separator.key-value", "white", None),
    ("js/ts import keyword", "keyword.operator.expression.import", "bright_blue", None),
    ("math js/ts", "support.constant.math", "yellow", None),
    ("math property js/ts", "support.constant.property.math", "bright_yellow", None),
    ("js/ts variable.other.constant", "variable.other.constant", "yellow", None),
    ("java type", ["storage.type.annotation.java", "storage.type.object.array.java"], "yellow", None),
    ("java source", "source.java", "bright_magenta", None),
    ("java modifier.import", "punctuation.section.block.begin.java,punctuation.section.block.end.java,punctuation.definition.method-parameters.begin.java,punctuation.definition.method-parameters.end.java,meta.method.identifier.java,punctuation.section.method.begin.java,punctuation.section.method.end.java,punctuation.terminator.java,punctuation.section.class.begin.java,punctuation.section.class.end.java,punctuation.section.inner-class.begin.java,punctuation.section.inner-class.end.java,meta.method-call.java,punctuation.section.class.begin.bracket.curly.java,punctuation.section.class.end.bracket.curly.java,punctuation.section.method.begin.bracket.curly.java,punctuation.section.method.end.bracket.curly.java,punctuation.separator.period.java,punctuation.bracket.angle.java,punctuation.definition.annotation.java,meta.method.body.java", "white", None),
    ("java modifier.import", "meta.method.java", "bright_blue", None),
    ("java modifier.import", "storage.modifier.import.java,storage.type.java,storage.type.generic.java", "yellow", None),
    ("java instanceof", "keyword.operator.instanceof.java", "bright_red", None),
    ("java variable.name", "meta.definition.variable.name.java", "bright_magenta", None),
    ("operator logical", "keyword.operator.logical", "bright_cyan", None),
    ("operator bitwise", "keyword.operator.bitwise", "bright_cyan", None),
    ("operator channel", "keyword.operator.channel", "bright_cyan", None),
    ("support.constant.property-value.scss", "support.constant.property-value.scss,support.constant.property-value.css", "bright_yellow", None),
    ("CSS/SCSS/LESS Operators", "keyword.operator.css,keyword.operator.scss,keyword.operator.less", "bright_cyan", None),
    ("css color standard name", "support.constant.color.w3c-standard-color-name.css,support.constant.color.w3c-standard-color-name.scss", "bright_yellow", None),
    ("css comma", "punctuation.separator.list.comma.css", "white", None),
    ("css attribute-name.id", "support.constant.color.w3c-standard-color-name.css", "bright_yellow", None),
    ("css property-name", "support.type.vendored.property-name.css", "bright_cyan", None),
    ("js/ts module", "support.module.node,support.type.object.module,support.module.node", "yellow", None),
    ("entity.name.type.module", "entity.name.type.module", "yellow", None),
    ("js variable readwrite", "variable.other.readwrite,meta.object-literal.key,support.variable.property,support.variable.object.process,support.variable.object.node", "bright_magenta", None),
    ("js/ts json", "support.constant.json", "bright_yellow", None),
    ("js/ts Keyword", ["keyword.operator.expression.instanceof", "keyword.operator.new", "keyword.operator.ternary", "keyword.operator.optional", "keyword.operator.expression.keyof"], "bright_red", None),
    ("js/ts console", "support.type.object.console", "bright_magenta", None),
    ("js/ts support.variable.property.process", "support.variable.property.process", "bright_yellow", None),
    ("js console function", "entity.name.function,support.function.console", "bright_blue", None),
    ("keyword.operator.misc.rust", "keyword.operator.misc.rust", "white", None),
    ("keyword.operator.sigil.rust", "keyword.operator.sigil.rust", "bright_red", None),
    ("operator", "keyword.operator.delete", "bright_red", None),
    ("js dom", "support.type.object.dom", "bright_cyan", None),
    ("js dom variable", "support.variable.dom,support.variable.property.dom", "bright_magenta", None),
    ("keyword.operator", "keyword.operator.arithmetic,keyword.operator.comparison,keyword.operator.decrement,keyword.operator.increment,keyword.operator.relational", "bright_cyan", None),
    ("C operator assignment", "keyword.operator.assignment.c,keyword.operator.comparison.c,keyword.operator.c,keyword.operator.increment.c,keyword.operator.decrement.c,keyword.operator.bitwise.shift.c,keyword.operator.assignment.cpp,keyword.operator.comparison.cpp,keyword.operator.cpp,keyword.operator.increment.cpp,keyword.operator.decrement.cpp,keyword.operator.bitwise.shift.cpp", "bright_red", None),
    ("Punctuation", "punctuation.separator.delimiter", "white", None),
    ("Other punctuation .c", "punctuation.separator.c,punctuation.separator.cpp", "bright_red", None),
    ("C type posix-reserved", "support.type.posix-reserved.c,support.type.posix-reserved.cpp", "bright_cyan", None),
    ("keyword.operator.sizeof.c", "keyword.operator.sizeof.c,keyword.operator.sizeof.cpp", "bright_red", None),
    ("python parameter", "variable.parameter.function.language.python", "bright_yellow", None),
    ("python type", "support.type.python", "bright_cyan", None),
    ("python logical", "keyword.operator.logical.python", "bright_red", None),
    ("pyCs", "variable.parameter.function.python", "bright_yellow", None),
    ("python block", "punctuation.definition.arguments.begin.python,punctuation.definition.arguments.end.python,punctuation.separator.arguments.python,punctuation.definition.list.begin.python,punctuation.definition.list.end.python", "white", None),
    ("python function-call.generic", "meta.function-call.generic.python", "bright_blue", None),
    ("python placeholder reset to normal string", "constant.character.format.placeholder.other.python", "bright_yellow", None),
    ("Operators", "keyword.operator", "white", None),
    ("Compound Assignment Operators", "keyword.operator.assignment.compound", "bright_red", None),
    ("Compound Assignment Operators js/ts", "keyword.operator.assignment.compound.js,keyword.operator.assignment.compound.ts", "bright_cyan", None),
    ("Keywords", "keyword", "bright_red", None),
    ("Namespaces", "entity.name.namespace", "yellow", None),
    ("Variables", "variable", "bright_magenta", None),
    ("Variables", "variable.c", "white", None),
    ("Language variables", "variable.language", "yellow", None),
    ("Java Variables", "token.variable.parameter.java", "white", None),
    ("Java Imports", "import.storage.java", "yellow", None),
    ("Packages", "token.package.keyword", "bright_red", None),
    ("Packages", "token.package", "white", None),
    ("Functions", ["entity.name.function", "meta.require", "support.function.any-method", "variable.function"], "bright_blue", None),
    ("Classes", "entity.name.type.namespace", "yellow", None),
    ("Classes", "support.class, entity.name.type.class", "yellow", None),
    ("Class name", "entity.name.class.identifier.namespace.type", "yellow", None),
    ("Class name", ["entity.name.class", "variable.other.class.js", "variable.other.class.ts"], "yellow", None),
    ("Class name php", "variable.other.class.php", "bright_magenta", None),
    ("Type Name", "entity.name.type", "yellow", None),
    ("Keyword Control", "keyword.control", "bright_red", None),
    ("Control Elements", "control.elements, keyword.operator.less", "bright_yellow", None),
    ("Methods", "keyword.other.special-method", "bright_blue", None),
    ("Storage", "storage", "bright_red", None),
    ("Storage JS TS", "token.storage", "bright_red", None),
    ("Source Js Keyword Operator Delete,source Js Keyword Operator In,source Js Keyword Operator Of,source Js Keyword Operator Instanceof,source Js Keyword Operator New,source Js Keyword Operator Typeof,source Js Keyword Operator Void", "keyword.operator.expression.delete,keyword.operator.expression.in,keyword.operator.expression.of,keyword.operator.expression.instanceof,keyword.operator.new,keyword.operator.expression.typeof,keyword.operator.expression.void", "bright_red", None),
    ("Java Storage", "token.storage.type.java", "yellow", None),
    ("Support", "support.function", "bright_cyan", None),
    ("Support type", "support.type.property-name", "white", None),
    ("Support type", "support.constant.property-value", "white", None),
    ("Support type", "support.constant.font-name", "bright_yellow", None),
    ("Meta tag", "meta.tag", "white", None),
    ("Strings", "string", "green", None),
    ("Inherited Class", "entity.other.inherited-class", "yellow", None),
    ("Constant other symbol", "constant.other.symbol", "bright_cyan", None),
    ("Integers", "constant.numeric", "bright_yellow", None),
    ("Constants", "constant", "bright_yellow", None),
    ("Constants", "punctuation.definition.constant", "bright_yellow", None),
    ("Tags", "entity.name.tag", "bright_magenta", None),
    ("Attributes", "entity.other.attribute-name", "bright_yellow", None),
    ("Attribute IDs", "entity.other.attribute-name.id", "bright_blue", ""),
    ("Attribute class", "entity.other.attribute-name.class.css", "bright_yellow", ""),
    ("Selector", "meta.selector", "bright_red", None),
    ("Headings", "markup.heading", "bright_magenta", None),
    ("Headings", "markup.heading punctuation.definition.heading, entity.name.section", "bright_blue", None),
    ("Units", "keyword.other.unit", "bright_magenta", None),
    ("Bold", "markup.bold,todo.bold", "bright_yellow", None),
    ("Bold", "punctuation.definition.bold", "yellow", None),
    ("markup Italic", "markup.italic, punctuation.definition.italic,todo.emphasis", "bright_red", None),
    ("emphasis md", "emphasis md", "bright_red", None),
    ("[VSCODE-CUSTOM] Markdown headings", "entity.name.section.markdown", "bright_magenta", None),
    ("[VSCODE-CUSTOM] Markdown heading Punctuation Definition", "punctuation.definition.heading.markdown", "bright_magenta", None),
    ("punctuation.definition.list.begin.markdown", "punctuation.definition.list.begin.markdown", "bright_magenta", None),
    ("[VSCODE-CUSTOM] Markdown heading setext", "markup.heading.setext", "white", None),
    ("[VSCODE-CUSTOM] Markdown Punctuation Definition Bold", "punctuation.definition.bold.markdown", "bright_yellow", None),
    ("[VSCODE-CUSTOM] Markdown Inline Raw", "markup.inline.raw.markdown", "green", None),
    ("[VSCODE-CUSTOM] Markdown Inline Raw", "markup.inline.raw.string.markdown", "green", None),
    ("[VSCODE-CUSTOM] Markdown List Punctuation Definition", "punctuation.definition.list.markdown", "bright_magenta", None),
    ("[VSCODE-CUSTOM] Markdown Punctuation Definition String", ["punctuation.definition.string.begin.markdown", "punctuation.definition.string.end.markdown", "punctuation.definition.metadata.markdown"], "bright_magenta", None),
    ("beginning.punctuation.definition.list.markdown", ["beginning.punctuation.definition.list.markdown"], "bright_magenta", None),
    ("[VSCODE-CUSTOM] Markdown Punctuation Definition Link", "punctuation.definition.metadata.markdown", "bright_magenta", None),
    ("[VSCODE-CUSTOM] Markdown Underline Link/Image", "markup.underline.link.markdown,markup.underline.link.image.markdown", "bright_red", None),
    ("[VSCODE-CUSTOM] Markdown Link Title/Description", "string.other.link.title.markdown,string.other.link.description.markdown", "bright_blue", None),
    ("Regular Expressions", "string.regexp", "bright_cyan", None),
    ("Escape Characters", "constant.character.escape", "bright_cyan", None),
    ("Embedded", "punctuation.section.embedded, variable.interpolation", "bright_magenta", None),
    ("Embedded", "punctuation.section.embedded.begin,punctuation.section.embedded.end", "bright_red", None),
    ("illegal", "invalid.illegal", "pure_white", None),
    ("illegal", "invalid.illegal.bad-ampersand.html", "white", None),
    ("Broken", "invalid.broken", "pure_white", None),
    ("Deprecated", "invalid.deprecated", "pure_white", None),
    ("Unimplemented", "invalid.unimplemented", "pure_white", None),
    ("Source Json Meta Structure Dictionary Json > String Quoted Json", "source.json meta.structure.dictionary.json > string.quoted.json", "bright_magenta", None),
    ("Source Json Meta Structure Dictionary Json > String Quoted Json > Punctuation String", "source.json meta.structure.dictionary.json > string.quoted.json > punctuation.string", "bright_magenta", None),
    ("Source Json Meta Structure Dictionary Json > Value Json > String Quoted Json,source Json Meta Structure Array Json > Value Json > String Quoted Json,source Json Meta Structure Dictionary Json > Value Json > String Quoted Json > Punctuation,source Json Meta Structure Array Json > Value Json > String Quoted Json > Punctuation", "source.json meta.structure.dictionary.json > value.json > string.quoted.json,source.json meta.structure.array.json > value.json > string.quoted.json,source.json meta.structure.dictionary.json > value.json > string.quoted.json > punctuation,source.json meta.structure.array.json > value.json > string.quoted.json > punctuation", "green", None),
    ("Source Json Meta Structure Dictionary Json > Constant Language Json,source Json Meta Structure Array Json > Constant Language Json", "source.json meta.structure.dictionary.json > constant.language.json,source.json meta.structure.array.json > constant.language.json", "bright_cyan", None),
    ("[VSCODE-CUSTOM] JSON Property Name", "support.type.property-name.json", "bright_magenta", None),
    ("[VSCODE-CUSTOM] JSON Punctuation for Property Name", "support.type.property-name.json punctuation", "bright_magenta", None),
    ("laravel blade tag", "text.html.laravel-blade source.php.embedded.line.html entity.name.tag.laravel-blade", "bright_red", None),
    ("laravel blade @", "text.html.laravel-blade source.php.embedded.line.html support.constant.laravel-blade", "bright_red", None),
    ("use statement for other classes", "support.other.namespace.use.php,support.other.namespace.use-as.php,support.other.namespace.php,entity.other.alias.php,meta.interface.php", "yellow", None),
    ("error suppression", "keyword.operator.error-control.php", "bright_red", None),
    ("php instanceof", "keyword.operator.type.php", "bright_red", None),
    ("style double quoted array index normal begin", "punctuation.section.array.begin.php", "white", None),
    ("style double quoted array index normal end", "punctuation.section.array.end.php", "white", None),
    ("php illegal.non-null-typehinted", "invalid.illegal.non-null-typehinted.php", "error", None),
    ("php types", "storage.type.php,meta.other.type.phpdoc.php,keyword.other.type.php,keyword.other.array.phpdoc.php", "yellow", None),
    ("php call-function", "meta.function-call.php,meta.function-call.object.php,meta.function-call.static.php", "bright_blue", None),
    ("php function-resets", "punctuation.definition.parameters.begin.bracket.round.php,punctuation.definition.parameters.end.bracket.round.php,punctuation.separator.delimiter.php,punctuation.section.scope.begin.php,punctuation.section.scope.end.php,punctuation.terminator.expression.php,punctuation.definition.arguments.begin.bracket.round.php,punctuation.definition.arguments.end.bracket.round.php,punctuation.definition.storage-type.begin.bracket.round.php,punctuation.definition.storage-type.end.bracket.round.php,punctuation.definition.array.begin.bracket.round.php,punctuation.definition.array.end.bracket.round.php,punctuation.definition.begin.bracket.round.php,punctuation.definition.end.bracket.round.php,punctuation.definition.begin.bracket.curly.php,punctuation.definition.end.bracket.curly.php,punctuation.definition.section.switch-block.end.bracket.curly.php,punctuation.definition.section.switch-block.start.bracket.curly.php,punctuation.definition.section.switch-block.begin.bracket.curly.php,punctuation.definition.section.switch-block.end.bracket.curly.php", "white", None),
    ("support php constants", "support.constant.core.rust", "bright_yellow", None),
    ("support php constants", "support.constant.ext.php,support.constant.std.php,support.constant.core.php,support.constant.parser-token.php", "bright_yellow", None),
    ("php goto", "entity.name.goto-label.php,support.other.php", "bright_blue", None),
    ("php logical/bitwise operator", "keyword.operator.logical.php,keyword.operator.bitwise.php,keyword.operator.arithmetic.php", "bright_cyan", None),
    ("php regexp operator", "keyword.operator.regexp.php", "bright_red", None),
    ("php comparison", "keyword.operator.comparison.php", "bright_cyan", None),
    ("php heredoc/nowdoc", "keyword.operator.heredoc.php,keyword.operator.nowdoc.php", "bright_red", None),
    ("python function decorator @", "meta.function.decorator.python", "bright_blue", None),
    ("python function support", "support.token.decorator.python,meta.function.decorator.identifier.python", "bright_cyan", None),
    ("parameter function js/ts", "function.parameter", "white", None),
    ("brace function", "function.brace", "white", None),
    ("parameter function ruby cs", "function.parameter.ruby, function.parameter.cs", "white", None),
    ("constant.language.symbol.ruby", "constant.language.symbol.ruby", "bright_cyan", None),
    ("rgb-value", "rgb-value", "bright_cyan", None),
    ("rgb value", "inline-color-decoration rgb-value", "bright_yellow", None),
    ("rgb value less", "less rgb-value", "bright_yellow", None),
    ("sass selector", "selector.sass", "bright_magenta", None),
    ("ts primitive/builtin types", "support.type.primitive.ts,support.type.builtin.ts,support.type.primitive.tsx,support.type.builtin.tsx", "yellow", None),
    ("block scope", "block.scope.end,block.scope.begin", "white", None),
    ("cs storage type", "storage.type.cs", "yellow", None),
    ("cs local variable", "entity.name.variable.local.cs", "bright_magenta", None),
    (None, "token.info-token", "bright_blue", None),
    (None, "token.warn-token", "bright_yellow", None),
    (None, "token.error-token", "error", None),
    (None, "token.debug-token", "bright_red", None),
    ("String interpolation", ["punctuation.definition.template-expression.begin", "punctuation.definition.template-expression.end", "punctuation.section.embedded"], "bright_red", None),
    ("Reset JavaScript string interpolation expression", ["meta.template.expression"], "white", None),
    ("Import module JS", ["keyword.operator.module"], "bright_red", None),
    ("js Flowtype", ["support.type.type.flowtype"], "bright_blue", None),
    ("js Flow", ["support.type.primitive"], "yellow", None),
    ("js class prop", ["meta.property.object"], "bright_magenta", None),
    ("js func parameter", ["variable.parameter.function.js"], "bright_magenta", None),
    ("js template literals begin", ["keyword.other.template.begin"], "green", None),
    ("js template literals end", ["keyword.other.template.end"], "green", None),
    ("js template literals variable braces begin", ["keyword.other.substitution.begin"], "green", None),
    ("js template literals variable braces end", ["keyword.other.substitution.end"], "green", None),
    ("js operator.assignment", ["keyword.operator.assignment"], "bright_cyan", None),
    ("go operator", ["keyword.operator.assignment.go"], "yellow", None),
    ("go operator", ["keyword.operator.arithmetic.go", "keyword.operator.address.go"], "bright_red", None),
    ("Go package name", ["entity.name.package.go"], "yellow", None),
    ("elm prelude", ["support.type.prelude.elm"], "bright_cyan", None),
    ("elm constant", ["support.constant.elm"], "bright_yellow", None),
    ("template literal", ["punctuation.quasi.element"], "bright_red", None),
    ("html/pug (jade) escaped characters and entities", ["constant.character.entity"], "bright_magenta", None),
    ("styling css pseudo-elements/classes to be able to differentiate from classes which are the same colour", ["entity.other.attribute-name.pseudo-element", "entity.other.attribute-name.pseudo-class"], "bright_cyan", None),
    ("Clojure globals", ["entity.global.clojure"], "yellow", None),
    ("Clojure symbols", ["meta.symbol.clojure"], "bright_magenta", None),
    ("Clojure constants", ["constant.keyword.clojure"], "bright_cyan", None),
    ("CoffeeScript Function Argument", ["meta.arguments.coffee", "variable.parameter.function.coffee"], "bright_magenta", None),
    ("Ini Default Text", ["source.ini"], "green", None),
    ("Makefile prerequisities", ["meta.scope.prerequisites.makefile"], "bright_magenta", None),
    ("Makefile text colour", ["source.makefile"], "yellow", None),
    ("Groovy import names", ["storage.modifier.import.groovy"], "yellow", None),
    ("Groovy Methods", ["meta.method.groovy"], "bright_blue", None),
    ("Groovy Variables", ["meta.definition.variable.name.groovy"], "bright_magenta", None),
    ("Groovy Inheritance", ["meta.definition.class.inherited.classes.groovy"], "green", None),
    ("HLSL Semantic", ["support.variable.semantic.hlsl"], "yellow", None),
    ("HLSL Types", ["support.type.texture.hlsl", "support.type.sampler.hlsl", "support.type.object.hlsl", "support.type.object.rw.hlsl", "support.type.fx.hlsl", "support.type.object.hlsl"], "bright_red", None),
    ("SQL Variables", ["text.variable", "text.bracketed"], "bright_magenta", None),
    ("types", ["support.type.swift", "support.type.vb.asp"], "yellow", None),
    ("heading 1, keyword", ["entity.name.function.xi"], "yellow", None),
    ("heading 2, callable", ["entity.name.class.xi"], "bright_cyan", None),
    ("heading 3, property", ["constant.character.character-class.regexp.xi"], "bright_magenta", None),
    ("heading 4, type, class, interface", ["constant.regexp.xi"], "bright_red", None),
    ("heading 5, enums, preprocessor, constant, decorator", ["keyword.control.xi"], "bright_cyan", None),
    ("heading 6, number", ["invalid.xi"], "white", None),
    ("string", ["beginning.punctuation.definition.quote.markdown.xi"], "green", None),
    ("comments", ["beginning.punctuation.definition.list.markdown.xi"], "blue", None),
    ("link", ["constant.character.xi"], "bright_blue", None),
    ("accent", ["accent.xi"], "bright_blue", None),
    ("wikiword", ["wikiword.xi"], "bright_yellow", None),
    ("language operators like '+', '-' etc", ["constant.other.color.rgb-value.xi"], "pure_white", None),
    ("elements to dim", ["punctuation.definition.tag.xi"], "blue", None),
    ("C++/C#", ["entity.name.label.cs", "entity.name.scope-resolution.function.call", "entity.name.scope-resolution.function.definition"], "yellow", None),
    ("Markdown underscore-style headers", ["entity.name.label.cs", "markup.heading.setext.1.markdown", "markup.heading.setext.2.markdown"], "bright_magenta", None),
    ("meta.brace.square", [" meta.brace.square"], "white", None),
    ("Comments", "comment, punctuation.definition.comment", "blue", "italic"),
    ("[VSCODE-CUSTOM] Markdown Quote", "markup.quote.markdown", "blue", None),
    ("punctuation.definition.block.sequence.item.yaml", "punctuation.definition.block.sequence.item.yaml", "white", None),
    (None, ["constant.language.symbol.elixir"], "bright_cyan", None),
    ("js/ts italic", "entity.other.attribute-name.js,entity.other.attribute-name.ts,entity.other.attribute-name.jsx,entity.other.attribute-name.tsx,variable.parameter,variable.language.super", None, "italic"),
    ("comment", "comment.line.double-slash,comment.block.documentation", None, "italic"),
    ("Python Keyword Control", "keyword.control.import.python,keyword.control.flow.python", None, "italic"),
    ("markup.italic.markdown", "markup.italic.markdown", None, "italic"),
]

# VS Code UI colors: key → value
# Values are one of:
#   - "@palette_key"         → resolve from palette
#   - "@palette_key:aa"      → resolve + append alpha hex
#   - "#rrggbb" / "#rrggbbaa" → literal
VSCODE_UI_COLORS = OrderedDict([
    ("foreground", "@white"),
    ("focusBorder", "@bright_blue"),
    ("selection.background", "@selection"),
    ("scrollbar.shadow", "#000000"),
    ("activityBar.foreground", "@pure_white"),
    ("activityBar.background", "@bg_raised"),
    ("activityBar.inactiveForeground", {"dark": "#ffffff66", "light": "#00000066"}),
    ("activityBarBadge.foreground", "#ffffff"),
    ("activityBarBadge.background", "@blue"),
    ("sideBar.background", "@bg_mid"),
    ("sideBar.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("sideBarSectionHeader.background", "#00000000"),
    ("sideBarSectionHeader.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("sideBarSectionHeader.border", {"dark": "#cccccc33", "light": "#44444433"}),
    ("sideBarTitle.foreground", {"dark": "#bbbbbb", "light": "#555555"}),
    ("list.inactiveSelectionBackground", {"dark": "#37373d", "light": "#c8cec0"}),
    ("list.inactiveSelectionForeground", {"dark": "#cccccc", "light": "#444444"}),
    ("list.hoverBackground", {"dark": "#2a2d2e", "light": "#dbd0c2"}),
    ("list.hoverForeground", {"dark": "#cccccc", "light": "#444444"}),
    ("list.activeSelectionBackground", "@selection"),
    ("list.activeSelectionForeground", "@pure_white"),
    ("tree.indentGuidesStroke", "#585858"),
    ("list.dropBackground", "@bg_raised"),
    ("list.highlightForeground", "@bright_white"),
    ("list.focusBackground", "@selection"),
    ("list.focusForeground", {"dark": "#cccccc", "light": "#444444"}),
    ("listFilterWidget.background", "#653723"),
    ("listFilterWidget.outline", "#00000000"),
    ("listFilterWidget.noMatchesOutline", "#be1100"),
    ("statusBar.foreground", "@pure_white"),
    ("statusBar.background", "@bg_raised"),
    ("statusBarItem.hoverBackground", {"dark": "#ffffff1f", "light": "#0000001f"}),
    ("statusBar.debuggingBackground", "#cc6633"),
    ("statusBar.debuggingForeground", "#ffffff"),
    ("statusBar.noFolderBackground", "#68217a"),
    ("statusBar.noFolderForeground", "#ffffff"),
    ("statusBarItem.remoteBackground", "#16825d"),
    ("statusBarItem.remoteForeground", "#ffffff"),
    ("titleBar.activeBackground", "@bg_raised"),
    ("titleBar.activeForeground", {"dark": "#cccccc", "light": "#444444"}),
    ("titleBar.inactiveBackground", {"dark": "#3c3c3c99", "light": "#dbd0c299"}),
    ("titleBar.inactiveForeground", {"dark": "#cccccc99", "light": "#44444499"}),
    ("titleBar.border", "#00000000"),
    ("menubar.selectionForeground", {"dark": "#cccccc", "light": "#444444"}),
    ("menubar.selectionBackground", {"dark": "#ffffff1a", "light": "#0000001a"}),
    ("menu.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("menu.background", "@bg_raised"),
    ("menu.selectionForeground", "@pure_white"),
    ("menu.selectionBackground", "@selection"),
    ("menu.selectionBorder", "#00000000"),
    ("menu.separatorBackground", {"dark": "#bbbbbb", "light": "#555555"}),
    ("menu.border", {"dark": "#00000085", "light": "#00000025"}),
    ("button.background", "#35597b"),
    ("button.foreground", "#ffffff"),
    ("button.hoverBackground", "@blue"),
    ("button.secondaryForeground", "@pure_white"),
    ("button.secondaryBackground", "@selection"),
    ("button.secondaryHoverBackground", "@cursor"),
    ("input.background", "@bg_mid"),
    ("input.border", "#00000000"),
    ("input.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("inputOption.activeBackground", {"dark": "#ffffff22", "light": "#00000022"}),
    ("inputOption.activeBorder", "#007acc55"),
    ("inputOption.activeForeground", "#ffffff"),
    ("input.placeholderForeground", {"dark": "#a6a6a6", "light": "#777777"}),
    ("textLink.foreground", "#3794ff"),
    ("editor.background", "@bg_deep"),
    ("editor.foreground", "@white"),
    ("editorLineNumber.foreground", {"dark": "#858585", "light": "#999999"}),
    ("editorCursor.foreground", {"dark": "#aeafad", "light": "#555555"}),
    ("editorCursor.background", "#000000"),
    ("editor.selectionBackground", "@selection"),
    ("editor.inactiveSelectionBackground", {"dark": "#3a3d4188", "light": "#c8cec088"}),
    ("editorWhitespace.foreground", {"dark": "#e3e4e229", "light": "#33333329"}),
    ("editor.selectionHighlightBackground", "@yellow:45"),
    ("editor.selectionHighlightBorder", "@yellow"),
    ("editor.findMatchBackground", "@selection"),
    ("editor.findMatchBorder", "#74879f"),
    ("editor.findMatchHighlightBackground", "#ea5c0055"),
    ("editor.findMatchHighlightBorder", "#ffffff00"),
    ("editor.findRangeHighlightBackground", "#3a3d4166"),
    ("editor.findRangeHighlightBorder", "#ffffff00"),
    ("editor.rangeHighlightBackground", "#ffffff0b"),
    ("editor.rangeHighlightBorder", "#ffffff00"),
    ("editor.hoverHighlightBackground", "#264f7840"),
    ("editor.wordHighlightStrongBackground", "#004972b8"),
    ("editor.wordHighlightBackground", "#575757b8"),
    ("editor.lineHighlightBackground", {"dark": "#ffffff1a", "light": "#0000000d"}),
    ("editor.lineHighlightBorder", "#4d4324"),
    ("editorLineNumber.activeForeground", {"dark": "#c6c6c6", "light": "#444444"}),
    ("editorLink.activeForeground", "#4e94ce"),
    ("editorIndentGuide.background1", "#aa0000"),
    ("editorIndentGuide.background2", "#aa6600"),
    ("editorIndentGuide.background3", "#c0c000"),
    ("editorIndentGuide.background4", "#008844"),
    ("editorIndentGuide.background5", "#3333ff"),
    ("editorIndentGuide.background6", "#9933cc"),
    ("editorIndentGuide.activeBackground1", "#aa0000f0"),
    ("editorIndentGuide.activeBackground2", "#aa6600f0"),
    ("editorIndentGuide.activeBackground3", "#c0c000f0"),
    ("editorIndentGuide.activeBackground4", "#008844f0"),
    ("editorIndentGuide.activeBackground5", "#3333fff0"),
    ("editorIndentGuide.activeBackground6", "#9933ccf0"),
    ("editorBracketHighlight.foreground1", "#aa0000"),
    ("editorBracketHighlight.foreground2", "#aa6600"),
    ("editorBracketHighlight.foreground3", "#c0c000"),
    ("editorBracketHighlight.foreground4", "#008844"),
    ("editorBracketHighlight.foreground5", "#3333ff"),
    ("editorBracketHighlight.foreground6", "#9933cc"),
    ("editorBracketPairGuide.background1", "#aa000088"),
    ("editorBracketPairGuide.background2", "#aa550088"),
    ("editorBracketPairGuide.background3", "#99990088"),
    ("editorBracketPairGuide.background4", "#00990088"),
    ("editorBracketPairGuide.background5", "#3333ff88"),
    ("editorBracketPairGuide.background6", "#99009988"),
    ("editorBracketPairGuide.activeBackground1", "#aa0000f0"),
    ("editorBracketPairGuide.activeBackground2", "#aa6600f0"),
    ("editorBracketPairGuide.activeBackground3", "#c0c000f0"),
    ("editorBracketPairGuide.activeBackground4", "#008844f0"),
    ("editorBracketPairGuide.activeBackground5", "#3333fff0"),
    ("editorBracketPairGuide.activeBackground6", "#9933ccf0"),
    ("editorBracketHighlight.unexpectedBracket.foreground", "@pure_white"),
    ("editorRuler.foreground", "#5a5a5a"),
    ("editorBracketMatch.background", "#0064001a"),
    ("editorBracketMatch.border", "#888888"),
    ("editor.foldBackground", "#264f784d"),
    ("editorOverviewRuler.background", "#25252500"),
    ("editorOverviewRuler.border", "#7f7f7f4d"),
    ("editorError.foreground", "#f48771"),
    ("editorError.background", "#B73A3400"),
    ("editorError.border", "#ffffff00"),
    ("editorWarning.foreground", "#cca700"),
    ("editorWarning.background", "#A9904000"),
    ("editorWarning.border", "#ffffff00"),
    ("editorInfo.foreground", "#75beff"),
    ("editorInfo.background", "#4490BF00"),
    ("editorInfo.border", "#4490BF00"),
    ("editorGutter.background", "@bg_raised"),
    ("editorGutter.modifiedBackground", "#0c7d9d"),
    ("editorGutter.addedBackground", "#587c0c"),
    ("editorGutter.deletedBackground", "#94151b"),
    ("editorGutter.foldingControlForeground", {"dark": "#c5c5c5", "light": "#777777"}),
    ("editorCodeLens.foreground", "#999999"),
    ("editorGroup.border", "#444444"),
    ("diffEditor.insertedTextBackground", "#55b96e33"),
    ("diffEditor.removedTextBackground", "#ff000033"),
    ("diffEditor.border", "#444444"),
    ("panel.background", "@bg_deep"),
    ("panel.border", "#80808059"),
    ("panelTitle.activeBorder", {"dark": "#e7e7e7", "light": "#444444"}),
    ("panelTitle.activeForeground", {"dark": "#e7e7e7", "light": "#333333"}),
    ("panelTitle.inactiveForeground", {"dark": "#e7e7e799", "light": "#44444499"}),
    ("badge.background", "@blue"),
    ("badge.foreground", "#ffffff"),
    ("terminal.foreground", "@white"),
    ("terminal.selectionBackground", {"dark": "#ffffff40", "light": "#00000020"}),
    ("terminalCursor.background", "@cursor"),
    ("terminalCursor.foreground", "@pure_white"),
    ("terminal.border", "#80808059"),
    ("terminal.ansiBlack", "@black"),
    ("terminal.ansiBlue", "@blue"),
    ("terminal.ansiBrightBlack", "@bright_black"),
    ("terminal.ansiBrightBlue", "@bright_blue"),
    ("terminal.ansiBrightCyan", "@bright_cyan"),
    ("terminal.ansiBrightGreen", "@bright_green"),
    ("terminal.ansiBrightMagenta", "@bright_magenta"),
    ("terminal.ansiBrightRed", "@bright_red"),
    ("terminal.ansiBrightWhite", "@bright_white"),
    ("terminal.ansiBrightYellow", "@bright_yellow"),
    ("terminal.ansiCyan", "@cyan"),
    ("terminal.ansiGreen", "@green"),
    ("terminal.ansiMagenta", "@magenta"),
    ("terminal.ansiRed", "@red"),
    ("terminal.ansiWhite", "@white"),
    ("terminal.ansiYellow", "@yellow"),
    ("breadcrumb.background", "@bg_mid"),
    ("breadcrumb.foreground", {"dark": "#cccccccc", "light": "#444444cc"}),
    ("breadcrumb.focusForeground", {"dark": "#e0e0e0", "light": "#333333"}),
    ("editorGroupHeader.tabsBackground", "@bg_deep"),
    ("tab.activeForeground", "@pure_white"),
    ("tab.border", "#252526"),
    ("tab.activeBackground", "@bg_deep"),
    ("tab.activeBorder", "#00000000"),
    ("tab.activeBorderTop", "@accent"),
    ("tab.inactiveBackground", "@selection"),
    ("tab.inactiveForeground", {"dark": "#ffffff80", "light": "#00000080"}),
    ("scrollbarSlider.background", {"dark": "#79797966", "light": "#79797944"}),
    ("scrollbarSlider.hoverBackground", {"dark": "#646464b3", "light": "#64646480"}),
    ("scrollbarSlider.activeBackground", {"dark": "#bfbfbf66", "light": "#44444466"}),
    ("progressBar.background", "@bright_blue"),
    ("widget.shadow", "#0000005c"),
    ("editorWidget.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("editorWidget.background", "@bg_mid"),
    ("editorWidget.resizeBorder", "#5F5F5F"),
    ("pickerGroup.border", "#3f3f46"),
    ("pickerGroup.foreground", "@bright_blue"),
    ("debugToolBar.background", "@bg_mid"),
    ("debugToolBar.border", "#474747"),
    ("notifications.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("notifications.background", "@bg_mid"),
    ("notificationToast.border", "#474747"),
    ("notificationsErrorIcon.foreground", "#f48771"),
    ("notificationsWarningIcon.foreground", "#cca700"),
    ("notificationsInfoIcon.foreground", "#75beff"),
    ("notificationCenter.border", "#474747"),
    ("notificationCenterHeader.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("notificationCenterHeader.background", "#362920"),
    ("notifications.border", "#303031"),
    ("gitDecoration.addedResourceForeground", "@green"),
    ("gitDecoration.conflictingResourceForeground", "#6c6cc4"),
    ("gitDecoration.deletedResourceForeground", {"dark": "#e3b3b2", "light": "#a83e3c"}),
    ("gitDecoration.ignoredResourceForeground", "#627383"),
    ("gitDecoration.modifiedResourceForeground", {"dark": "#ffd7ae", "light": "#8a6a20"}),
    ("gitDecoration.stageDeletedResourceForeground", {"dark": "#e3b3b2", "light": "#a83e3c"}),
    ("gitDecoration.stageModifiedResourceForeground", {"dark": "#ffd7ae", "light": "#8a6a20"}),
    ("gitDecoration.submoduleResourceForeground", "@bright_blue"),
    ("gitDecoration.untrackedResourceForeground", {"dark": "#e4a1cd", "light": "#7d3e69"}),
    ("editorMarkerNavigation.background", "#362920"),
    ("editorMarkerNavigationError.background", "#f48771"),
    ("editorMarkerNavigationWarning.background", "#cca700"),
    ("editorMarkerNavigationInfo.background", "#75beff"),
    ("merge.currentHeaderBackground", "#36736688"),
    ("merge.currentContentBackground", "#27403B88"),
    ("merge.incomingHeaderBackground", "#8f6d3988"),
    ("merge.incomingContentBackground", "#4b3f2888"),
    ("merge.commonHeaderBackground", "#38383888"),
    ("merge.commonContentBackground", "#28282888"),
    ("editorSuggestWidget.background", "@bg_mid"),
    ("editorSuggestWidget.border", "#454545"),
    ("editorSuggestWidget.foreground", {"dark": "#d4d4d4", "light": "#444444"}),
    ("editorSuggestWidget.highlightForeground", "@bright_white"),
    ("editorSuggestWidget.selectedBackground", "#362920"),
    ("editorHoverWidget.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("editorHoverWidget.background", "@bg_mid"),
    ("editorHoverWidget.border", "#454545"),
    ("peekView.border", "#007acc"),
    ("peekViewEditor.background", "#362920"),
    ("peekViewEditorGutter.background", "@selection"),
    ("peekViewEditor.matchHighlightBackground", "#ba680099"),
    ("peekViewEditor.matchHighlightBorder", "#ec911c"),
    ("peekViewResult.background", "@bg_mid"),
    ("peekViewResult.fileForeground", "#ffffff"),
    ("peekViewResult.lineForeground", {"dark": "#bbbbbb", "light": "#555555"}),
    ("peekViewResult.matchHighlightBackground", "#ea5c004d"),
    ("peekViewResult.selectionBackground", "#3399ff33"),
    ("peekViewResult.selectionForeground", "#ffffff"),
    ("peekViewTitle.background", "#1b1b1b"),
    ("peekViewTitleDescription.foreground", {"dark": "#ccccccb3", "light": "#444444b3"}),
    ("peekViewTitleLabel.foreground", "#ffffff"),
    ("icon.foreground", "@white"),
    ("checkbox.background", "@bg_mid"),
    ("checkbox.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("checkbox.border", "#00000000"),
    ("dropdown.background", "@bg_mid"),
    ("dropdown.foreground", {"dark": "#cccccc", "light": "#444444"}),
    ("dropdown.border", "#00000000"),
    ("minimapGutter.addedBackground", "#587c0c"),
    ("minimapGutter.modifiedBackground", "#0c7d9d"),
    ("minimapGutter.deletedBackground", "#94151b"),
    ("minimap.findMatchHighlight", "@selection:88"),
    ("minimap.selectionHighlight", "@selection:88"),
    ("minimap.errorHighlight", "#f48771"),
    ("minimap.warningHighlight", "#cca700"),
    ("minimap.background", "@bg_deep"),
    ("sideBar.dropBackground", "@bg_raised"),
    ("editorGroup.emptyBackground", "@bg_deep"),
    ("panelSection.border", "#80808059"),
    ("statusBarItem.activeBackground", {"dark": "#FFFFFF25", "light": "#00000025"}),
    ("settings.headerForeground", "@white"),
    ("settings.focusedRowBackground", {"dark": "#ffffff07", "light": "#00000007"}),
    ("walkThrough.embeddedEditorBackground", "#00000050"),
    ("breadcrumb.activeSelectionForeground", {"dark": "#e0e0e0", "light": "#333333"}),
    ("editorGutter.commentRangeForeground", {"dark": "#c5c5c5", "light": "#777777"}),
    ("debugExceptionWidget.background", "@bg_mid"),
    ("debugExceptionWidget.border", "#474747"),
    ("tab.selectedBorderTop", "@accent"),
    ("tab.selectedBackground", "@bg_deep"),
    ("tab.selectedForeground", "@pure_white"),
    ("tab.dragAndDropBorder", "@yellow"),
    ("activityBarTop.foreground", "@pure_white"),
    ("activityBarTop.inactiveForeground", {"dark": "#ffffff66", "light": "#00000066"}),
    ("activityBarTop.activeBorder", "@pure_white"),
    ("activityBarTop.background", "@bg_raised"),
    ("activityBarTop.activeBackground", {"dark": "#ffffff1a", "light": "#0000001a"}),
    ("activityBarTop.dropBorder", "@pure_white"),
    ("scmGraph.foreground1", "@green"),
    ("scmGraph.foreground2", "@bright_blue"),
    ("scmGraph.foreground3", "@yellow"),
    ("scmGraph.foreground4", "@magenta"),
    ("scmGraph.foreground5", "@bright_red"),
    ("git.blame.editorDecorationForeground", "@bright_black"),
    ("editorGhostText.foreground", "@bright_black:88"),
    ("editorGhostText.background", "#00000000"),
    ("editorGhostText.border", "#00000000"),
    ("terminalCommandGuide.foreground", "@bright_black:44"),
    ("terminal.initialHintForeground", "@bright_black"),
    ("terminalStickyScroll.background", "@bg_mid"),
    ("terminalStickyScroll.border", "#80808059"),
    ("editorStickyScroll.background", "@bg_mid"),
    ("editorStickyScroll.border", "#80808059"),
    ("editorStickyScroll.shadow", "#0000005c"),
    ("editorStickyScrollHover.background", "@bg_raised"),
    ("sideBarStickyScroll.background", "@bg_mid"),
    ("sideBarStickyScroll.border", "#80808059"),
    ("sideBarStickyScroll.shadow", "#0000005c"),
    ("panelStickyScroll.background", "@bg_mid"),
    ("panelStickyScroll.border", "#80808059"),
    ("panelStickyScroll.shadow", "#0000005c"),
    ("diffEditor.unchangedRegionBackground", "@bg_raised"),
    ("diffEditor.unchangedRegionForeground", "@bright_black"),
    ("diffEditor.unchangedRegionShadow", "#0000005c"),
    ("diffEditor.unchangedCodeBackground", "@bg_mid:44"),
    ("diffEditor.move.border", "@yellow:88"),
    ("diffEditor.moveActive.border", "@yellow"),
    ("multiDiffEditor.headerBackground", "@bg_raised"),
    ("multiDiffEditor.background", "@bg_deep"),
    ("multiDiffEditor.border", "#80808059"),
    ("editorGutter.addedSecondaryBackground", "#587c0c88"),
    ("editorGutter.modifiedSecondaryBackground", "#0c7d9d88"),
    ("editorGutter.deletedSecondaryBackground", "#94151b88"),
    ("chat.requestBackground", "@bg_mid"),
    ("chat.requestBorder", "#80808059"),
    ("chat.slashCommandBackground", "@blue:44"),
    ("chat.slashCommandForeground", "@bright_blue"),
    ("chat.avatarBackground", "@bg_raised"),
    ("chat.avatarForeground", "@white"),
    ("chat.editedFileForeground", "@yellow"),
    ("inlineChat.background", "@bg_mid"),
    ("inlineChat.foreground", "@white"),
    ("inlineChat.border", "#80808059"),
    ("inlineChat.shadow", "#0000005c"),
    ("inlineChatInput.border", "#80808059"),
    ("inlineChatInput.focusBorder", "@bright_blue"),
    ("inlineChatInput.placeholderForeground", {"dark": "#a6a6a6", "light": "#777777"}),
    ("inlineChatInput.background", "@bg_deep"),
    ("inlineChatDiff.inserted", "#55b96e33"),
    ("inlineChatDiff.removed", "#ff000033"),
    ("inlineEdit.modifiedChangedLineBackground", "#55b96e22"),
    ("inlineEdit.modifiedChangedTextBackground", "#55b96e44"),
    ("inlineEdit.originalChangedLineBackground", "#ff000022"),
    ("inlineEdit.originalChangedTextBackground", "#ff000044"),
    ("inlineEdit.modifiedBorder", "@green:88"),
    ("inlineEdit.originalBorder", "@red:88"),
    ("editorLightBulbAi.foreground", "@yellow"),
    ("commandCenter.debuggingBackground", "#cc663344"),
    ("statusBarItem.offlineBackground", "#68217a"),
    ("statusBarItem.offlineForeground", "#ffffff"),
    ("editorBracketMatch.foreground", "@white"),
])


# ══════════════════════════════════════════════════════════════════════════════
# IntelliJ theme data
# ══════════════════════════════════════════════════════════════════════════════

# The IntelliJ theme.json is stored verbatim since its "ui" section references
# named colors (not hex) and is complex/nested. We generate the "colors" section
# from palette and keep "ui" and "icons" as static data.

INTELLIJ_THEME_COLORS = OrderedDict([
    ("background", "bg_deep"),
    ("backgroundEmpty", "#251000"),
    ("backgroundHighlights", "bg_raised"),
    ("backgroundHighlightsShading", "#473020ab"),
    ("primaryText", "white"),
    ("inverseBackground", "#c0a055"),
    ("inverseBackgroundHighlights", "yellow"),
    ("inversePrimaryText", "#653723"),
    ("inverseSecondaryText", "bg_raised"),
    ("inverseEmphasizedText", "bg_mid"),
    ("secondaryText", "yellow"),
    ("backgroundHighlightsShade1", "#000000"),
    ("backgroundHighlightsShade2", "selection"),
    ("backgroundHighlightsShade2Shading", "@selection:c3"),
    ("emphasizedContent", "#46303c"),
    ("brightYellow", "yellow"),
    ("brightGreen", "bright_green"),
    ("brightBlue", "bright_blue"),
    ("brightViolet", "bright_magenta"),
    ("brightOrange", "#ff9944"),
    ("brightRose", "#ff7e7c"),
    ("yellow", "#926000"),
    ("green", "#006600"),
    ("blue", "#3333aa"),
    ("violet", "#770055"),
    ("orange", "#aa4400"),
    ("rose", "#880000"),
    ("maskColor", "#0d0d0d"),
    ("blueTransparent", "#3333aa66"),
    ("greenTransparent", "#00660055"),
    ("grayTransparent", "#66666666"),
    ("orangeTransparent", "#bb440055"),
    ("roseTransparent", "#88000066"),
    ("violetTransparent", "#77005577"),
    ("yellowTransparent", "#92800055"),
])

# The IntelliJ ui section is static — it references named colors, not hex.
# We store it as a Python dict and serialize to JSON.
INTELLIJ_UI = {
    "*": {
        "background": "background",
        "foreground": "primaryText",
        "infoForeground": "secondaryText",
        "selectionBackground": "inverseEmphasizedContent",
        "selectionForeground": "inverseBackground",
        "selectionInactiveBackground": "backgroundHighlightsShade1",
        "selectionBackgroundInactive": "backgroundHighlightsShade1",
        "lightSelectionBackground": "backgroundHighlightsShade1",
        "lightSelectionForeground": "primaryText",
        "lightSelectionInactiveBackground": "backgroundHighlights",
        "lightSelectionInactiveForeground": "primaryText",
        "disabledBackground": "background",
        "inactiveBackground": "background",
        "disabledForeground": "yellow",
        "disabledText": "yellow",
        "inactiveForeground": "secondaryText",
        "acceleratorForeground": "primaryText",
        "acceleratorSelectionForeground": "primaryText",
        "errorForeground": "brightRose",
        "borderColor": "emphasizedContent",
        "disabledBorderColor": "backgroundEmpty",
        "focusColor": "yellow",
        "focusedBorderColor": "emphasizedContent",
        "separatorForeground": "secondaryText",
        "separatorColor": "backgroundHighlightsShade1",
        "lineSeparatorColor": "emphasizedContent",
        "modifiedItemForeground": "brightBlue",
    },
    "ActionButton": {
        "hoverBackground": "backgroundHighlightsShade1",
        "hoverBorderColor": "yellow",
        "pressedBackground": "backgroundEmpty",
        "pressedBorderColor": "yellow",
    },
    "Button": {
        "startBackground": "backgroundEmpty",
        "endBackground": "backgroundEmpty",
        "startBorderColor": "yellow",
        "endBorderColor": "yellow",
        "shadowColor": "background",
        "default": {
            "foreground": "primaryText",
            "startBackground": "blue",
            "endBackground": "blue",
            "startBorderColor": "brightBlue",
            "endBorderColor": "brightBlue",
            "focusedBorderColor": "primaryText",
            "focusColor": "yellow",
            "shadowColor": "background",
        },
    },
    "Borders": {
        "color": "backgroundHighlights",
        "ContrastBorderColor": "background",
    },
    "CheckBox": {"background": "background"},
    "ComboBox": {
        "nonEditableBackground": "backgroundHighlightsShade1",
        "background": "background",
        "foreground": "primaryText",
        "disabledForeground": "inverseBackground",
        "modifiedItemForeground": "brightBlue",
        "selectionForeground": "brightYellow",
        "selectionBackground": "backgroundEmpty",
        "ArrowButton": {
            "iconColor": "emphasizedContent",
            "disabledIconColor": "primaryText",
            "nonEditableBackground": "backgroundHighlightsShade1",
        },
    },
    "ComboPopup.border": "1,1,1,1,#653723",
    "CompletionPopup": {"matchForeground": "violet"},
    "Component": {
        "errorFocusColor": "rose",
        "inactiveErrorFocusColor": "emphasizedContent",
        "warningFocusColor": "orange",
        "inactiveWarningFocusColor": "emphasizedContent",
        "iconColor": "secondaryText",
        "hoverIconColor": "brightYellow",
    },
    "Counter": {"background": "primaryText", "foreground": "background"},
    "DebuggerPopup.borderColor": "yellow",
    "DefaultTabs": {
        "background": "backgroundHighlightsShade1",
        "borderColor": "backgroundHighlightsShade1",
        "hoverBackground": "backgroundHighlightsShade2",
        "inactiveUnderlineColor": "backgroundHighlightsShade2",
        "underlineColor": "backgroundHighlightsShade2",
        "underlinedTabBackground": "backgroundHighlights",
        "underlinedTabForeground": "primaryText",
        "underlineHeight": 5,
    },
    "DragAndDrop": {"areaForeground": "primaryText", "areaBackground": "violet"},
    "Editor": {
        "background": "background",
        "foreground": "emphasizedContent",
        "shortcutForeground": "brightGreen",
    },
    "EditorPane.inactiveBackground": "background",
    "EditorTabs": {
        "borderColor": "background",
        "underlineColor": "brightYellow",
        "inactiveUnderlineColor": "yellow",
        "background": "backgroundHighlightsShade1",
        "underlinedTabBackground": "background",
        "underlinedTabForeground": "primaryText",
        "inactiveColoredFileBackground": "backgroundHighlightsShade1",
        "underlineHeight": 4,
        "underlinedBorderColor": "brightYellow",
        "inactiveUnderlinedTabBorderColor": "yellow",
        "inactiveUnderlinedTabBackground": "backgroundHighlightsShade1",
    },
    "FileColor": {
        "Blue": "blueTransparent",
        "Green": "greenTransparent",
        "Gray": "grayTransparent",
        "Orange": "orangeTransparent",
        "Rose": "roseTransparent",
        "Violet": "violetTransparent",
        "Yellow": "yellowTransparent",
    },
    "InplaceRefactoringPopup.borderColor": "yellow",
    "Link": {
        "activeForeground": "brightBlue",
        "hoverForeground": "brightGreen",
        "pressedForeground": "brightBlue",
        "visitedForeground": "brightBlue",
    },
    "NavBar.borderColor": "yellow",
    "Notification": {
        "background": "backgroundHighlightsShade1",
        "borderColor": "backgroundHighlights",
        "errorForeground": "primaryText",
        "errorBackground": "rose",
        "errorBorderColor": "rose",
        "MoreButton.innerBorderColor": "green",
        "ToolWindow": {
            "informativeForeground": "primaryText",
            "informativeBackground": "background",
            "informativeBorderColor": "backgroundHighlights",
            "warningForeground": "brightOrange",
            "warningBackground": "background",
            "warningBorderColor": "orange",
            "errorForeground": "brightRose",
            "errorBackground": "background",
            "errorBorderColor": "rose",
        },
    },
    "NotificationsToolwindow": {"newNotification.background": "background"},
    "Panel": {"background": "background"},
    "ParameterInfo": {
        "background": "backgroundHighlightsShade1",
        "foreground": "primaryText",
        "infoForeground": "secondaryText",
        "currentOverloadBackground": "backgroundHighlights",
        "currentParameterForeground": "primaryText",
    },
    "Plugins": {
        "SearchField.background": "background",
        "SectionHeader.background": "backgroundHighlights",
        "tagBackground": "backgroundHighlightsShade1",
        "tagForeground": "brightBlue",
        "Button": {
            "installForeground": "primaryText",
            "installBackground": "backgroundEmpty",
            "installBorderColor": "yellow",
            "installFillForeground": "primaryText",
            "installFillBackground": "backgroundEmpty",
            "updateForeground": "primaryText",
            "updateBackground": "blue",
            "updateBorderColor": "brightBlue",
        },
    },
    "Popup": {
        "paintBorder": True,
        "borderColor": "backgroundHighlightsShade1",
        "inactiveBorderColor": "backgroundHighlights",
        "Toolbar.borderColor": "yellow",
        "Header.activeBackground": "backgroundHighlightsShade1",
        "Header.inactiveBackground": "backgroundHighlightsShade1",
        "Advertiser": {
            "foreground": "secondaryText",
            "borderColor": "backgroundHighlightsShade1",
            "borderInsets": "4,8,3,0",
        },
    },
    "PopupMenu": {"borderWidth": 1, "borderInsets": "4,1,4,1"},
    "ProgressBar": {
        "trackColor": "backgroundHighlightsShade1",
        "progressColor": "blue",
        "indeterminateStartColor": "blue",
        "indeterminateEndColor": "brightBlue",
        "failedColor": "rose",
        "failedEndColor": "brightRose",
        "passedColor": "green",
        "passedEndColor": "brightGreen",
    },
    "SearchEverywhere": {
        "Header.background": "backgroundHighlights",
        "Tab": {
            "selectedForeground": "primaryText",
            "selectedBackground": "backgroundHighlightsShade1",
        },
        "SearchField": {"background": "background", "borderColor": "yellow"},
        "Advertiser.foreground": "background",
    },
    "SearchMatch": {"startBackground": "primaryText", "endBackground": "secondaryText"},
    "SpeedSearch": {
        "foreground": "primaryText",
        "borderColor": "yellow",
        "background": "background",
        "errorForeground": "brightRose",
    },
    "Island": {
        "borderColor": "emphasizedContent",
        "arc": 20,
        "borderWidth": 5,
        "inactiveAlpha": 0.44,
    },
    "Islands": 1,
    "MainWindow.background": "background",
    "MainToolbar.borderColor": "#100c0000",
    "StatusBar.borderColor": "#100c0000",
    "ToolWindow.Stripe.borderColor": "#100c0000",
    "TabbedPane": {
        "underlineColor": "backgroundHighlightsShade2",
        "disabledUnderlineColor": "backgroundHighlightsShade2",
        "contentAreaColor": "backgroundHighlights",
        "background": "backgroundHighlightsShade1",
        "foreground": "primaryText",
        "disabledForeground": "primaryText",
        "focusColor": "backgroundHighlights",
        "hoverColor": "backgroundHighlightsShade2",
    },
    "TableHeader.cellBorder": "3,0,3,0",
    "Table.stripeColor": "backgroundHighlightsShade1",
    "TextArea": {
        "background": "backgroundHighlights",
        "selectionBackground": "backgroundHighlightsShade2",
    },
    "TextField": {
        "background": "backgroundHighlights",
        "selectionBackground": "backgroundHighlightsShade2",
    },
    "ToggleButton": {
        "onForeground": "primaryText",
        "onBackground": "blue",
        "offForeground": "secondaryText",
        "offBackground": "background",
        "buttonColor": "backgroundEmpty",
        "borderColor": "yellow",
    },
    "ToolTip": {
        "background": "backgroundHighlightsShade1",
        "Actions.background": "background",
    },
    "ToolWindow": {
        "background": "background",
        "Header": {
            "background": "backgroundHighlightsShade1",
            "inactiveBackground": "backgroundHighlights",
            "borderColor": "backgroundHighlightsShade2",
        },
        "HeaderTab": {
            "underlineColor": "brightYellow",
            "inactiveUnderlineColor": "brightYellow",
            "underlineHeight": 4,
            "selectedInactiveBackground": "background",
            "hoverBackground": "backgroundHighlightsShade2",
            "hoverInactiveBackground": "backgroundHighlightsShade1",
        },
        "Button": {
            "hoverBackground": "backgroundHighlightsShade1",
            "selectedBackground": "backgroundHighlightsShade2",
            "selectedForeground": "brightYellow",
        },
    },
    "Tree": {"rowHeight": 20, "background": "backgroundEmpty"},
    "ValidationTooltip": {
        "errorBackground": "rose",
        "errorBorderColor": "rose",
        "warningBackground": "orange",
        "warningBorderColor": "orange",
    },
    "VersionControl": {
        "Log.Commit": {
            "currentBranchBackground": "green",
            "unmatchedForeground": "brightRose",
        },
        "FileHistory.Commit.selectedBranchBackground": "backgroundHighlightsShade2",
    },
    "WelcomeScreen": {
        "separatorColor": "backgroundHighlights",
        "Projects": {
            "background": "backgroundHighlights",
            "selectionBackground": "backgroundHighlightsShade1",
            "selectionInactiveBackground": "backgroundHighlightsShade1",
        },
    },
}

INTELLIJ_ICONS = {
    "ColorPalette": {
        "Checkbox.Background.Default.Dark": "backgroundHighlightsShade1",
        "Checkbox.Border.Default.Dark": "inversePrimaryText",
        "Checkbox.Foreground.Selected.Dark": "secondaryText",
        "Checkbox.Focus.Wide.Dark": "emphasizedContent",
        "Checkbox.Focus.Thin.Default.Dark": "primaryText",
        "Checkbox.Focus.Thin.Selected.Dark": "primaryText",
        "Checkbox.Background.Disabled.Dark": "backgroundHighlights",
        "Checkbox.Border.Disabled.Dark": "backgroundHighlightsShade1",
        "Checkbox.Foreground.Disabled.Dark": "secondaryText",
    }
}


# ══════════════════════════════════════════════════════════════════════════════
# IntelliJ color scheme XML data
# ══════════════════════════════════════════════════════════════════════════════

# <colors> section: name → hex (uppercase, no hash)
INTELLIJ_SCHEME_COLORS = OrderedDict([
    ("GUTTER_BACKGROUND", "bg_deep"),
    ("INDENT_GUIDE", "#312E24"),
    ("SELECTED_INDENT_GUIDE", "#312E24"),
    ("WHITESPACES", "#312E24"),
    ("SELECTION_BACKGROUND", "selection"),
    ("CARET_COLOR", "#AEAFAD"),
    ("LINE_NUMBERS_COLOR", "white"),
    ("CARET_ROW_COLOR", "#282419"),
    ("CONSOLE_BACKGROUND_KEY", "bg_deep"),
])

# <attributes> section: name → {property: value_or_palette_key, ...}
# FOREGROUND/BACKGROUND values that are palette keys get resolved.
# Others (FONT_TYPE, EFFECT_TYPE, ERROR_STRIPE_COLOR) are literals.
# This will be populated by --bootstrap from the existing XML.
# For now, we store a placeholder that will be filled in.
INTELLIJ_SCHEME_ATTRS = OrderedDict([
    ("BAD_CHARACTER", {"BACKGROUND": "6E3B3B"}),
    ("BREAKPOINT_ATTRIBUTES", {"BACKGROUND": "743D3D"}),
    ("BUILDOUT.KEY", {"FOREGROUND": "bright_red"}),
    ("BUILDOUT.KEY_VALUE_SEPARATOR", {"FOREGROUND": "white"}),
    ("BUILDOUT.LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("BUILDOUT.SECTION_NAME", {"FOREGROUND": "bright_yellow"}),
    ("BUILDOUT.VALUE", {"FOREGROUND": "green"}),
    ("CLASS_REFERENCE", {"FOREGROUND": "yellow"}),
    ("COFFEESCRIPT.BAD_CHARACTER", {"BACKGROUND": "6E3B3B"}),
    ("COFFEESCRIPT.BLOCK_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("COFFEESCRIPT.BOOLEAN", {"FOREGROUND": "bright_yellow"}),
    ("COFFEESCRIPT.BRACE", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.BRACKET", {"FOREGROUND": "white"}),
    ("COFFEESCRIPT.CLASS_NAME", {"FOREGROUND": "bright_blue"}),
    ("COFFEESCRIPT.COLON", {"FOREGROUND": "bright_red"}),
    ("COFFEESCRIPT.COMMA", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.DOT", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.ESCAPE_SEQUENCE", {"FOREGROUND": "bright_cyan"}),
    ("COFFEESCRIPT.EXISTENTIAL", {"FOREGROUND": "bright_red"}),
    ("COFFEESCRIPT.EXPRESSIONS_SUBSTITUTION_MARK", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.FUNCTION", {"FOREGROUND": "bright_red"}),
    ("COFFEESCRIPT.FUNCTION_BINDING", {"FOREGROUND": "bright_red"}),
    ("COFFEESCRIPT.FUNCTION_NAME", {"FOREGROUND": "bright_blue"}),
    ("COFFEESCRIPT.GLOBAL_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.HEREDOC_CONTENT", {"FOREGROUND": "green"}),
    ("COFFEESCRIPT.HEREDOC_ID", {"FOREGROUND": "green"}),
    ("COFFEESCRIPT.HEREGEX_CONTENT", {"FOREGROUND": "bright_cyan"}),
    ("COFFEESCRIPT.HEREGEX_ID", {"FOREGROUND": "bright_cyan"}),
    ("COFFEESCRIPT.JAVASCRIPT_ID", {"FOREGROUND": "green"}),
    ("COFFEESCRIPT.KEYWORD", {"FOREGROUND": "bright_red"}),
    ("COFFEESCRIPT.LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("COFFEESCRIPT.NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("COFFEESCRIPT.OBJECT_KEY", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.OPERATIONS", {"FOREGROUND": "bright_red"}),
    ("COFFEESCRIPT.PARENTHESIS", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.PROTOTYPE", {"FOREGROUND": "bright_blue"}),
    ("COFFEESCRIPT.RANGE", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.REGULAR_EXPRESSION_CONTENT", {"FOREGROUND": "bright_cyan"}),
    ("COFFEESCRIPT.REGULAR_EXPRESSION_FLAG", {"FOREGROUND": "bright_cyan"}),
    ("COFFEESCRIPT.REGULAR_EXPRESSION_ID", {"FOREGROUND": "bright_cyan"}),
    ("COFFEESCRIPT.SEMICOLON", {"FOREGROUND": "white"}),
    ("COFFEESCRIPT.SPLAT", {"FOREGROUND": "bright_magenta"}),
    ("COFFEESCRIPT.STRING", {"FOREGROUND": "green"}),
    ("COFFEESCRIPT.STRING_LITERAL", {"FOREGROUND": "green"}),
    ("COFFEESCRIPT.THIS", {"FOREGROUND": "yellow"}),
    ("CONDITIONALLY_NOT_COMPILED", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("CONSOLE_BLUE_OUTPUT", {"FOREGROUND": "blue"}),
    ("CONSOLE_CYAN_OUTPUT", {"FOREGROUND": "cyan"}),
    ("CONSOLE_ERROR_OUTPUT", {"FOREGROUND": "bright_red"}),
    ("CONSOLE_GRAY_OUTPUT", {"FOREGROUND": "bright_black"}),
    ("CONSOLE_GREEN_OUTPUT", {"FOREGROUND": "green"}),
    ("CONSOLE_MAGENTA_OUTPUT", {"FOREGROUND": "magenta"}),
    ("CONSOLE_NORMAL_OUTPUT", {"FOREGROUND": "white"}),
    ("CONSOLE_RED_OUTPUT", {"FOREGROUND": "red"}),
    ("CONSOLE_SYSTEM_OUTPUT", {"FOREGROUND": "bright_blue"}),
    ("CONSOLE_USER_INPUT", {"FOREGROUND": "bright_green", "FONT_TYPE": "2"}),
    ("CONSOLE_YELLOW_OUTPUT", {"FOREGROUND": "yellow"}),
    ("CSS.COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("CSS.FUNCTION", {"FOREGROUND": "bright_cyan"}),
    ("CSS.IDENT", {"FOREGROUND": "bright_yellow"}),
    ("CSS.NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("CSS.PROPERTY_NAME", {"FOREGROUND": "white"}),
    ("CSS.PROPERTY_VALUE", {"FOREGROUND": "68E868", "FONT_TYPE": "1"}),
    ("CSS.TAG_NAME", {"FOREGROUND": "bright_magenta"}),
    ("CSS.URL", {"FONT_TYPE": "2"}),
    ("CUSTOM_INVALID_STRING_ESCAPE_ATTRIBUTES", {"FOREGROUND": "68E868", "BACKGROUND": "481515"}),
    ("CUSTOM_KEYWORD1_ATTRIBUTES", {"FOREGROUND": "E3E3FF", "FONT_TYPE": "1"}),
    ("CUSTOM_KEYWORD2_ATTRIBUTES", {"FOREGROUND": "FDA5FF", "FONT_TYPE": "1"}),
    ("CUSTOM_KEYWORD3_ATTRIBUTES", {"FOREGROUND": "71D7D7", "FONT_TYPE": "1"}),
    ("CUSTOM_KEYWORD4_ATTRIBUTES", {"FOREGROUND": "FFC2C2", "FONT_TYPE": "1"}),
    ("CUSTOM_LINE_COMMENT_ATTRIBUTES", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("CUSTOM_MULTI_LINE_COMMENT_ATTRIBUTES", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("CUSTOM_NUMBER_ATTRIBUTES", {"FOREGROUND": "bright_yellow"}),
    ("CUSTOM_STRING_ATTRIBUTES", {"FOREGROUND": "green", "FONT_TYPE": "1"}),
    ("CUSTOM_VALID_STRING_ESCAPE_ATTRIBUTES", {"FOREGROUND": "bright_cyan", "FONT_TYPE": "1"}),
    ("Clojure Atom", {"FOREGROUND": "bright_red"}),
    ("Clojure Character", {"FOREGROUND": "green"}),
    ("Clojure Keyword", {"FOREGROUND": "bright_magenta"}),
    ("Clojure Line comment", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("Clojure Literal", {"FOREGROUND": "bright_magenta"}),
    ("Clojure Numbers", {"FOREGROUND": "bright_yellow"}),
    ("Clojure Strings", {"FOREGROUND": "green"}),
    ("DEFAULT_ATTRIBUTE", {"FOREGROUND": "bright_yellow"}),
    ("DEFAULT_BLOCK_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("DEFAULT_BRACES", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_BRACKETS", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_COMMA", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_CONSTANT", {"FOREGROUND": "bright_yellow"}),
    ("DEFAULT_DOC_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("DEFAULT_DOC_COMMENT_TAG", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("DEFAULT_DOC_MARKUP", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("DEFAULT_DOT", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_ENTITY", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_FUNCTION_CALL", {"FOREGROUND": "bright_cyan"}),
    ("DEFAULT_FUNCTION_DECLARATION", {"FOREGROUND": "bright_blue"}),
    ("DEFAULT_GLOBAL_VARIABLE", {"FOREGROUND": "bright_magenta", "FONT_TYPE": "2"}),
    ("DEFAULT_INSTANCE_FIELD", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_INSTANCE_METHOD", {"FOREGROUND": "bright_blue"}),
    ("DEFAULT_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("DEFAULT_LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("DEFAULT_LOCAL_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_METADATA", {"FOREGROUND": "white"}),
    ("DEFAULT_NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("DEFAULT_OPERATION_SIGN", {"FOREGROUND": "white"}),
    ("DEFAULT_PARAMETER", {"FONT_TYPE": "2"}),
    ("DEFAULT_PARENTHS", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_SEMICOLON", {"FOREGROUND": "bright_magenta"}),
    ("DEFAULT_STATIC_FIELD", {"FOREGROUND": "bright_magenta", "FONT_TYPE": "2"}),
    ("DEFAULT_STATIC_METHOD", {"FOREGROUND": "bright_blue"}),
    ("DEFAULT_STRING", {"FOREGROUND": "green"}),
    ("DEFAULT_TAG", {"FOREGROUND": "green"}),
    ("DEFAULT_VALID_STRING_ESCAPE", {"FOREGROUND": "bright_cyan"}),
    ("DEPRECATED_ATTRIBUTES", {"EFFECT_TYPE": "3", "EFFECT_COLOR": "C0C0C0"}),
    ("DJANGO_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("DJANGO_FILTER", {"FOREGROUND": "bright_cyan"}),
    ("DJANGO_ID", {"FOREGROUND": "bright_yellow"}),
    ("DJANGO_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("DJANGO_NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("DJANGO_STRING_LITERAL", {"FOREGROUND": "green"}),
    ("DJANGO_TAG_NAME", {"FOREGROUND": "bright_magenta"}),
    ("DJANGO_TAG_START_END", {"FOREGROUND": "bright_magenta"}),
    ("DUPLICATE_FROM_SERVER", {"BACKGROUND": "30322B"}),
    ("ENUM_CONST", {"FOREGROUND": "bright_cyan"}),
    ("ERRORS_ATTRIBUTES", {"EFFECT_TYPE": "2", "EFFECT_COLOR": "FF6667", "ERROR_STRIPE_COLOR": "FF0000"}),
    ("FOLLOWED_HYPERLINK_ATTRIBUTES", {"FOREGROUND": "C7C7FF", "BACKGROUND": "171717", "FONT_TYPE": "2", "EFFECT_TYPE": "1", "EFFECT_COLOR": "C7C7FF"}),
    ("First symbol in list", {"FOREGROUND": "bright_magenta", "FONT_TYPE": "1"}),
    ("GENERIC_SERVER_ERROR_OR_WARNING", {"EFFECT_TYPE": "2", "EFFECT_COLOR": "AA4E00", "ERROR_STRIPE_COLOR": "F49810"}),
    ("GHERKIN_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("GHERKIN_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("GHERKIN_OUTLINE_PARAMETER_SUBSTITUTION", {"FOREGROUND": "bright_magenta"}),
    ("GHERKIN_PYSTRING", {"FOREGROUND": "green"}),
    ("GHERKIN_REGEXP_PARAMETER", {"FOREGROUND": "green"}),
    ("GHERKIN_TABLE_HEADER_CELL", {"FOREGROUND": "bright_magenta"}),
    ("GHERKIN_TABLE_PIPE", {"FOREGROUND": "bright_red"}),
    ("GHERKIN_TAG", {"FOREGROUND": "bright_red"}),
    ("GO_BLOCK_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("GO_BUILTIN_CONSTANT", {"FOREGROUND": "bright_yellow"}),
    ("GO_BUILTIN_FUNCTION_CALL", {"FOREGROUND": "bright_cyan"}),
    ("GO_BUILTIN_VARIABLE", {"FOREGROUND": "bright_magenta", "FONT_TYPE": "2"}),
    ("GO_EXPORTED_FUNCTION", {"FOREGROUND": "bright_blue"}),
    ("GO_EXPORTED_FUNCTION_CALL", {"FOREGROUND": "bright_cyan"}),
    ("GO_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("GO_LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("GO_LOCAL_CONSTANT", {"FOREGROUND": "bright_yellow"}),
    ("GO_LOCAL_FUNCTION", {"FOREGROUND": "bright_blue"}),
    ("GO_LOCAL_FUNCTION_CALL", {"FOREGROUND": "bright_cyan"}),
    ("GO_METHOD_RECEIVER", {"FOREGROUND": "bright_magenta"}),
    ("GO_PACKAGE_EXPORTED_CONSTANT", {"FOREGROUND": "bright_yellow"}),
    ("GO_PACKAGE_LOCAL_CONSTANT", {"FOREGROUND": "bright_yellow"}),
    ("GQL_ID", {"FOREGROUND": "bright_yellow"}),
    ("GQL_INT_LITERAL", {"FOREGROUND": "bright_yellow"}),
    ("GQL_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("GQL_STRING_LITERAL", {"FOREGROUND": "green"}),
    ("HAML_CLASS", {"FOREGROUND": "bright_magenta"}),
    ("HAML_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("HAML_ID", {"FOREGROUND": "bright_magenta"}),
    ("HAML_PARENTHS", {"FOREGROUND": "bright_magenta"}),
    ("HAML_STRING", {"FOREGROUND": "green"}),
    ("HAML_STRING_INTERPOLATED", {"FOREGROUND": "green"}),
    ("HAML_TAG", {"FOREGROUND": "green"}),
    ("HAML_TAG_NAME", {"FOREGROUND": "white"}),
    ("HAML_WS_REMOVAL", {"FOREGROUND": "bright_magenta"}),
    ("HTML_ATTRIBUTE_NAME", {"FOREGROUND": "bright_yellow"}),
    ("HTML_ATTRIBUTE_VALUE", {"FOREGROUND": "green", "FONT_TYPE": "1"}),
    ("HTML_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("HTML_ENTITY_REFERENCE", {"FOREGROUND": "bright_magenta", "FONT_TYPE": "1"}),
    ("HTML_TAG", {"FOREGROUND": "green"}),
    ("HTML_TAG_NAME", {"FOREGROUND": "bright_magenta"}),
    ("HYPERLINK_ATTRIBUTES", {"FOREGROUND": "C7C7FF", "FONT_TYPE": "2", "EFFECT_TYPE": "1", "EFFECT_COLOR": "C7C7FF"}),
    ("IDENTIFIER_UNDER_CARET_ATTRIBUTES", {"BACKGROUND": "3C3C57", "ERROR_STRIPE_COLOR": "CCCCFF"}),
    ("IMPLICIT_ANONYMOUS_CLASS_PARAMETER_ATTRIBUTES", {"FOREGROUND": "FDA5FF"}),
    ("INFO_ATTRIBUTES", {"EFFECT_TYPE": "2", "EFFECT_COLOR": "343434", "ERROR_STRIPE_COLOR": "FFFFCC"}),
    ("INJECTED_LANGUAGE_FRAGMENT", {"BACKGROUND": "273627"}),
    ("INSTANCE_FIELD_ATTRIBUTES", {"FOREGROUND": "FDA5FF", "FONT_TYPE": "1"}),
    ("IVAR", {"FOREGROUND": "bright_magenta"}),
    ("JADE_FILE_PATH", {"FOREGROUND": "green"}),
    ("JADE_STATEMENTS", {"FOREGROUND": "bright_red"}),
    ("JAVA_BLOCK_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("JAVA_BRACES", {"FOREGROUND": "bright_magenta"}),
    ("JAVA_BRACKETS", {"FOREGROUND": "bright_magenta"}),
    ("JAVA_COMMA", {"FOREGROUND": "bright_magenta"}),
    ("JAVA_DOC_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("JAVA_DOC_MARKUP", {"BACKGROUND": "223F22"}),
    ("JAVA_DOC_TAG", {"FONT_TYPE": "1", "EFFECT_TYPE": "1", "EFFECT_COLOR": "807F80"}),
    ("JAVA_DOT", {"FOREGROUND": "bright_magenta"}),
    ("JAVA_INVALID_STRING_ESCAPE", {"FOREGROUND": "68E868", "BACKGROUND": "481515"}),
    ("JAVA_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("JAVA_LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("JAVA_NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("JAVA_OPERATION_SIGN", {"FOREGROUND": "white"}),
    ("JAVA_PARENTH", {"FOREGROUND": "bright_magenta"}),
    ("JAVA_SEMICOLON", {"FOREGROUND": "bright_magenta"}),
    ("JAVA_STRING", {"FOREGROUND": "green"}),
    ("JAVA_VALID_STRING_ESCAPE", {"FOREGROUND": "bright_cyan"}),
    ("JS.GLOBAL_VARIABLE", {"FOREGROUND": "bright_magenta", "FONT_TYPE": "2"}),
    ("JS.INSTANCE_MEMBER_FUNCTION", {"FOREGROUND": "bright_blue"}),
    ("JS.LOCAL_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("JS.PARAMETER", {"FONT_TYPE": "2"}),
    ("JS.REGEXP", {"FOREGROUND": "bright_cyan"}),
    ("LABEL", {"FOREGROUND": "bright_red"}),
    ("LESS_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("MACRONAME", {"FOREGROUND": "bright_blue"}),
    ("MATCHED_BRACE_ATTRIBUTES", {"BACKGROUND": "3A6DA0"}),
    ("NOT_USED_ELEMENT_ATTRIBUTES", {"EFFECT_COLOR": "aa4400", "EFFECT_TYPE": "4"}),
    ("OC.BLOCK_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("OC.CPP_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("OC.DIRECTIVE", {"FOREGROUND": "bright_red"}),
    ("OC.EXTERN_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("OC.GLOBAL_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("OC.KEYWORD", {"FOREGROUND": "bright_red"}),
    ("OC.LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("OC.LOCAL_VARIABLE", {"FOREGROUND": "bright_magenta"}),
    ("OC.MESSAGE_ARGUMENT", {"FOREGROUND": "bright_blue"}),
    ("OC.METHOD_DECLARATION", {"FOREGROUND": "bright_blue"}),
    ("OC.NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("OC.PARAMETER", {"FOREGROUND": "white"}),
    ("OC.PROPERTY", {"FOREGROUND": "bright_magenta"}),
    ("OC.SELFSUPERTHIS", {"FOREGROUND": "yellow"}),
    ("OC.STRING", {"FOREGROUND": "green"}),
    ("OC.STRUCT_FIELD", {"FOREGROUND": "bright_cyan"}),
    ("OC_FORMAT_TOKEN", {"FOREGROUND": "green"}),
    ("PHP_PARAMETER", {"FONT_TYPE": "2"}),
    ("PHP_VAR", {"FOREGROUND": "bright_magenta"}),
    ("PROTOCOL_REFERENCE", {"FOREGROUND": "yellow"}),
    ("PUPPET_BAD_CHARACTER", {"BACKGROUND": "6E3B3B"}),
    ("PUPPET_BLOCK_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("PUPPET_BRACES", {"FOREGROUND": "green"}),
    ("PUPPET_BRACKETS", {"FOREGROUND": "green"}),
    ("PUPPET_CLASS", {"FOREGROUND": "yellow"}),
    ("PUPPET_COMMA", {"FOREGROUND": "bright_magenta"}),
    ("PUPPET_DOT", {"FOREGROUND": "bright_magenta"}),
    ("PUPPET_ESCAPE_SEQUENCE", {"FOREGROUND": "bright_cyan"}),
    ("PUPPET_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("PUPPET_NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("PUPPET_OPERATION_SIGN", {"FOREGROUND": "bright_cyan"}),
    ("PUPPET_PARENTH", {"FOREGROUND": "green"}),
    ("PUPPET_REGEX", {"FOREGROUND": "bright_cyan"}),
    ("PUPPET_SEMICOLON", {"FOREGROUND": "bright_magenta"}),
    ("PUPPET_SQ_STRING", {"FOREGROUND": "green"}),
    ("PUPPET_STRING", {"FOREGROUND": "green"}),
    ("PUPPET_VARIABLE", {"FOREGROUND": "green"}),
    ("PUPPET_VARIABLE_INTERPOLATION", {"FOREGROUND": "green"}),
    ("PY.BRACES", {"FOREGROUND": "bright_magenta"}),
    ("PY.BRACKETS", {"FOREGROUND": "bright_magenta"}),
    ("PY.BUILTIN_NAME", {"FOREGROUND": "bright_cyan"}),
    ("PY.CLASS_DEFINITION", {"FOREGROUND": "yellow"}),
    ("PY.COMMA", {"FOREGROUND": "bright_magenta"}),
    ("PY.DECORATOR", {"FOREGROUND": "bright_blue"}),
    ("PY.DOC_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("PY.DOT", {"FOREGROUND": "bright_magenta"}),
    ("PY.FUNC_DEFINITION", {"FOREGROUND": "bright_blue"}),
    ("PY.KEYWORD", {"FOREGROUND": "bright_red"}),
    ("PY.LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("PY.NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("PY.OPERATION_SIGN", {"FOREGROUND": "white"}),
    ("PY.PARENTHS", {"FOREGROUND": "bright_magenta"}),
    ("PY.PREDEFINED_USAGE", {"FOREGROUND": "bright_cyan"}),
    ("PY.STRING", {"FOREGROUND": "green"}),
    ("PY.VALID_STRING_ESCAPE", {"FOREGROUND": "bright_cyan"}),
    ("REST.BOLD", {"FONT_TYPE": "1"}),
    ("REST.EXPLICIT", {"FOREGROUND": "bright_red"}),
    ("REST.FIELD", {"FOREGROUND": "bright_red"}),
    ("REST.FIXED", {"BACKGROUND": "48485F"}),
    ("REST.INLINE", {"BACKGROUND": "273627"}),
    ("REST.INTERPRETED", {"BACKGROUND": "4D5D3D"}),
    ("REST.ITALIC", {"FONT_TYPE": "2"}),
    ("REST.LINE_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("REST.REF.NAME", {"FOREGROUND": "green"}),
    ("REST.SECTION.HEADER", {"FOREGROUND": "bright_yellow"}),
    ("RHTML_COMMENT_ID", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("RHTML_EXPRESSION_END_ID", {"FOREGROUND": "bright_magenta"}),
    ("RHTML_EXPRESSION_START_ID", {"FOREGROUND": "bright_magenta"}),
    ("RHTML_OMIT_NEW_LINE_ID", {"FOREGROUND": "bright_magenta"}),
    ("RHTML_SCRIPTING_BACKGROUND_ID", {"FOREGROUND": "green"}),
    ("RHTML_SCRIPTLET_END_ID", {"FOREGROUND": "bright_magenta"}),
    ("RHTML_SCRIPTLET_START_ID", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_BRACKETS", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_COLON", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_COMMA", {"FOREGROUND": "green"}),
    ("RUBY_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("RUBY_CONSTANT", {"FOREGROUND": "bright_yellow"}),
    ("RUBY_CONSTANT_DECLARATION", {"FOREGROUND": "yellow"}),
    ("RUBY_CVAR", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_DOT", {"FOREGROUND": "green"}),
    ("RUBY_ESCAPE_SEQUENCE", {"FOREGROUND": "bright_cyan"}),
    ("RUBY_EXPR_IN_STRING", {"FOREGROUND": "green"}),
    ("RUBY_GVAR", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_HASH_ASSOC", {"FOREGROUND": "white"}),
    ("RUBY_HEREDOC_CONTENT", {"FOREGROUND": "green"}),
    ("RUBY_HEREDOC_ID", {"FOREGROUND": "green"}),
    ("RUBY_IDENTIFIER", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_INTERPOLATED_STRING", {"FOREGROUND": "green"}),
    ("RUBY_IVAR", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("RUBY_LINE_CONTINUATION", {"FOREGROUND": "white"}),
    ("RUBY_LOCAL_VAR_ID", {"FOREGROUND": "bright_magenta"}),
    ("RUBY_METHOD_NAME", {"FOREGROUND": "bright_blue"}),
    ("RUBY_NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("RUBY_OPERATION_SIGN", {"FOREGROUND": "white"}),
    ("RUBY_PARAMDEF_CALL", {"FOREGROUND": "bright_cyan"}),
    ("RUBY_PARAMETER_ID", {"FONT_TYPE": "2"}),
    ("RUBY_REGEXP", {"FOREGROUND": "bright_cyan"}),
    ("RUBY_SEMICOLON", {"FOREGROUND": "green"}),
    ("RUBY_SPECIFIC_CALL", {"FOREGROUND": "bright_red"}),
    ("RUBY_STRING", {"FOREGROUND": "green"}),
    ("RUBY_SYMBOL", {"FOREGROUND": "bright_cyan"}),
    ("RUBY_WORDS", {"FOREGROUND": "green"}),
    ("SASS_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("SASS_DEFAULT", {"FOREGROUND": "bright_red"}),
    ("SASS_EXTEND", {"FOREGROUND": "bright_red"}),
    ("SASS_FUNCTION", {"FOREGROUND": "bright_yellow"}),
    ("SASS_IDENTIFIER", {"FOREGROUND": "bright_yellow"}),
    ("SASS_IMPORTANT", {"FOREGROUND": "bright_red"}),
    ("SASS_KEYWORD", {"FOREGROUND": "bright_red"}),
    ("SASS_MIXIN", {"FOREGROUND": "bright_yellow"}),
    ("SASS_NUMBER", {"FOREGROUND": "bright_yellow"}),
    ("SASS_PROPERTY_NAME", {"FOREGROUND": "white"}),
    ("SASS_PROPERTY_VALUE", {"FOREGROUND": "bright_yellow"}),
    ("SASS_STRING", {"FOREGROUND": "green"}),
    ("SASS_TAG_NAME", {"FOREGROUND": "bright_red"}),
    ("SASS_URL", {"FOREGROUND": "bright_yellow"}),
    ("SASS_VARIABLE", {"FONT_TYPE": "2"}),
    ("SEARCH_RESULT_ATTRIBUTES", {"BACKGROUND": "4F4F82"}),
    ("SLIM_BAD_CHARACTER", {"FOREGROUND": "white"}),
    ("SLIM_CLASS", {"FOREGROUND": "bright_magenta"}),
    ("SLIM_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("SLIM_DOCTYPE_KWD", {"FOREGROUND": "bright_magenta"}),
    ("SLIM_FILTER", {"FOREGROUND": "bright_magenta"}),
    ("SLIM_ID", {"FOREGROUND": "bright_magenta"}),
    ("SLIM_INTERPOLATION", {"FOREGROUND": "green"}),
    ("SLIM_PARENTHS", {"FOREGROUND": "bright_magenta"}),
    ("SLIM_STRING_INTERPOLATED", {"FOREGROUND": "green"}),
    ("SLIM_TAG", {"FOREGROUND": "bright_magenta"}),
    ("SLIM_TAG_ATTR_KEY", {"FOREGROUND": "bright_yellow"}),
    ("SLIM_TAG_START", {"FOREGROUND": "green"}),
    ("SPY-JS.EXCEPTION", {"BACKGROUND": "713F3E", "EFFECT_TYPE": "2", "EFFECT_COLOR": "white"}),
    ("SPY-JS.FUNCTION_SCOPE", {"BACKGROUND": "2E2E1F", "EFFECT_TYPE": "2", "EFFECT_COLOR": "white"}),
    ("SPY-JS.PATH_LEVEL_ONE", {"BACKGROUND": "264326", "EFFECT_TYPE": "2", "EFFECT_COLOR": "white"}),
    ("SPY-JS.PATH_LEVEL_TWO", {"EFFECT_TYPE": "1", "EFFECT_COLOR": "white"}),
    ("SPY-JS.PROGRAM_SCOPE", {"BACKGROUND": "2B2B2B", "EFFECT_TYPE": "2", "EFFECT_COLOR": "white"}),
    ("STATIC_FIELD_ATTRIBUTES", {"FOREGROUND": "FDA5FF", "FONT_TYPE": "3"}),
    ("STATIC_METHOD_ATTRIBUTES", {"FONT_TYPE": "2"}),
    ("TAG_ATTR_KEY", {"FOREGROUND": "bright_yellow"}),
    ("TEXT", {"FOREGROUND": "white", "BACKGROUND": "bg_deep"}),
    ("TEXT_SEARCH_RESULT_ATTRIBUTES", {"BACKGROUND": "5F5F00", "ERROR_STRIPE_COLOR": "00FF00"}),
    ("TODO_DEFAULT_ATTRIBUTES", {"FOREGROUND": "C7C7FF", "FONT_TYPE": "3", "ERROR_STRIPE_COLOR": "FF"}),
    ("TYPEDEF", {"FOREGROUND": "bright_red"}),
    ("UNMATCHED_BRACE_ATTRIBUTES", {"BACKGROUND": "583535"}),
    ("WARNING_ATTRIBUTES", {"BACKGROUND": "4A3F10", "EFFECT_TYPE": "1", "EFFECT_COLOR": "white", "ERROR_STRIPE_COLOR": "FFFF00"}),
    ("WRITE_IDENTIFIER_UNDER_CARET_ATTRIBUTES", {"BACKGROUND": "472C47", "ERROR_STRIPE_COLOR": "FFCDFF"}),
    ("WRITE_SEARCH_RESULT_ATTRIBUTES", {"BACKGROUND": "623062"}),
    ("XML_ATTRIBUTE_NAME", {"FOREGROUND": "bright_yellow"}),
    ("XML_ATTRIBUTE_VALUE", {"FOREGROUND": "green"}),
    ("XML_ENTITY_REFERENCE", {"FOREGROUND": "bright_magenta"}),
    ("XML_PROLOGUE", {"FONT_TYPE": "2"}),
    ("XML_TAG", {"FOREGROUND": "green"}),
    ("XML_TAG_DATA", {"FONT_TYPE": "1"}),
    ("XML_TAG_NAME", {"FOREGROUND": "bright_magenta"}),
    ("YAML_COMMENT", {"FOREGROUND": "blue", "FONT_TYPE": "2"}),
    ("YAML_SCALAR_DSTRING", {"FOREGROUND": "green"}),
    ("YAML_SCALAR_KEY", {"FOREGROUND": "bright_magenta"}),
    ("YAML_SCALAR_LIST", {"FOREGROUND": "green"}),
    ("YAML_SCALAR_STRING", {"FOREGROUND": "green"}),
    ("YAML_SCALAR_VALUE", {"FOREGROUND": "green"}),
    ("YAML_SIGN", {"FOREGROUND": "white"}),
    ("YAML_TEXT", {"FOREGROUND": "green"}),
])


# ══════════════════════════════════════════════════════════════════════════════
# Generators
# ══════════════════════════════════════════════════════════════════════════════

def resolve_vscode_color(palette, ref, variant="dark"):
    """Resolve a VS Code color reference.
    '@key'              → palette[key]
    '@key:aa'           → palette[key] + 'aa'
    '#rrggbb'           → as-is
    {"dark":…,"light":…} → pick by variant, then resolve
    """
    if isinstance(ref, dict):
        ref = ref.get(variant, ref.get("dark", ""))
    if not ref.startswith("@"):
        return ref
    ref = ref[1:]  # strip @
    if ":" in ref:
        key, alpha = ref.split(":", 1)
        return palette[key] + alpha
    return palette[ref]


def generate_ghostty(palette, variant):
    """Generate Ghostty theme file."""
    p = palette
    name = p["_meta"]["name"]
    version = p["_meta"]["version"]
    variant_label = "" if variant == "dark" else " Light"

    lines = [
        f"# {name}{variant_label} v{version}",
        GENERATED_HEADER_HASH,
        f"# {'Warm cream' if variant == 'light' else 'Very dark warm brown'} background, desaturated tones, low blue",
        "",
    ]

    ansi_keys = [
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
        "bright_black", "bright_red", "bright_green", "bright_yellow",
        "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
    ]
    for i, key in enumerate(ansi_keys):
        lines.append(f"palette = {i}={p[key]}")

    lines.append(f"background = {p['bg_deep']}")
    lines.append(f"foreground = {p['white']}")
    lines.append(f"cursor-color = {p['cursor']}")
    lines.append(f"cursor-text = #000000")
    lines.append(f"selection-background = {p['terminal_selection_bg']}")
    lines.append(f"selection-foreground = {p['terminal_selection_fg']}")
    lines.append("")

    suffix = "Light" if variant == "light" else ""
    path = REPO / "ghostty" / f"LowGravitasZen{suffix}"
    path.write_text("\n".join(lines))
    print(f"  wrote {path.relative_to(REPO)}")
    return path


def generate_warp(palette, variant):
    """Generate Warp theme file."""
    p = palette
    version = p["_meta"]["version"]
    details = "lighter" if variant == "light" else "darker"
    variant_label = f" {variant}" if variant != "dark" else ""
    suffix = "_light" if variant == "light" else ""

    lines = [
        f"# Low Gravitas Zen{variant_label} v{version}",
        GENERATED_HEADER_HASH,
        f'accent: "{p["accent"]}"',
        f'background: "{p["bg_deep"]}"',
        f'foreground: "{p["white"]}"',
        f'details: "{details}"',
        "terminal_colors:",
        "  normal:",
        f'    black: "{p["black"]}"',
        f'    red: "{p["red"]}"',
        f'    green: "{p["green"]}"',
        f'    yellow: "{p["yellow"]}"',
        f'    blue: "{p["blue"]}"',
        f'    magenta: "{p["magenta"]}"',
        f'    cyan: "{p["cyan"]}"',
        f'    white: "{p["white"]}"',
        "  bright:",
        f'    black: "{p["bright_black"]}"',
        f'    red: "{p["bright_red"]}"',
        f'    green: "{p["bright_green"]}"',
        f'    yellow: "{p["bright_yellow"]}"',
        f'    blue: "{p["bright_blue"]}"',
        f'    magenta: "{p["bright_magenta"]}"',
        f'    cyan: "{p["bright_cyan"]}"',
        f'    white: "{p["bright_white"]}"',
        "",
    ]

    path = REPO / "warp" / f"low_gravitas_zen{suffix}_theme.yaml"
    path.write_text("\n".join(lines))
    print(f"  wrote {path.relative_to(REPO)}")
    return path


def _iterm_color_entry(name, hex_color, alpha=1.0):
    """Generate an iTerm2 plist color entry."""
    r, g, b = hex_to_rgb(hex_color)
    return (
        f"\t<key>{name}</key>\n"
        f"\t<dict>\n"
        f"\t\t<key>Alpha Component</key>\n"
        f"\t\t<real>{alpha}</real>\n"
        f"\t\t<key>Blue Component</key>\n"
        f"\t\t<real>{b}</real>\n"
        f"\t\t<key>Color Space</key>\n"
        f"\t\t<string>sRGB</string>\n"
        f"\t\t<key>Green Component</key>\n"
        f"\t\t<real>{g}</real>\n"
        f"\t\t<key>Red Component</key>\n"
        f"\t\t<real>{r}</real>\n"
        f"\t</dict>"
    )


def generate_iterm(palette, variant):
    """Generate iTerm2 .itermcolors plist file."""
    p = palette
    suffix = "Light" if variant == "light" else ""

    ansi_keys = [
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
        "bright_black", "bright_red", "bright_green", "bright_yellow",
        "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
    ]

    # iTerm2 sorts Ansi keys alphabetically: 0, 1, 10, 11, ..., 15, 2, 3, ..., 9
    ansi_order = sorted(range(16), key=lambda i: f"Ansi {i} Color")

    entries = []
    for idx in ansi_order:
        entries.append(_iterm_color_entry(f"Ansi {idx} Color", p[ansi_keys[idx]]))

    extra = [
        ("Background Color", p["bg_deep"], 1.0),
        ("Badge Color", "#ff2600", 0.5),
        ("Bold Color", p["white"], 1.0),
        ("Cursor Color", p["cursor"], 1.0),
        ("Cursor Guide Color", "#b3ecff", 0.25),
        ("Cursor Text Color", "#000000", 1.0),
        ("Foreground Color", p["white"], 1.0),
        ("Link Color", "#005bbb", 1.0),
        ("Selected Text Color", p["terminal_selection_fg"], 1.0),
        ("Selection Color", p["terminal_selection_bg"], 1.0),
    ]
    for name, color, alpha in extra:
        entries.append(_iterm_color_entry(name, color, alpha))

    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        + "\n".join(entries) + "\n"
        '</dict>\n'
        '</plist>\n'
    )

    path = REPO / "iTerm2" / f"LowGravitasZen{suffix}.itermcolors"
    path.write_text(content)
    print(f"  wrote {path.relative_to(REPO)}")
    return path


def generate_vscode(palette, variant):
    """Generate VS Code color theme JSON."""
    p = palette
    variant_label = " Light" if variant == "light" else ""
    theme_type = "light" if variant == "light" else "dark"

    # Build theme structure
    theme = OrderedDict()
    theme["name"] = f"Low Gravitas Zen{variant_label}"
    theme["type"] = theme_type
    theme["semanticHighlighting"] = True

    # Semantic token colors
    sem = OrderedDict()
    for key, pal_key in VSCODE_SEMANTIC_TOKENS.items():
        sem[key] = {"foreground": p[pal_key]}
    theme["semanticTokenColors"] = sem

    # Token colors
    tc_list = []
    for name, scope, pal_key, font_style in VSCODE_TOKEN_COLORS:
        entry = OrderedDict()
        if name is not None:
            entry["name"] = name
        entry["scope"] = scope
        settings = OrderedDict()
        if font_style is not None:
            settings["fontStyle"] = font_style
        if pal_key is not None:
            settings["foreground"] = p[pal_key]
        entry["settings"] = settings
        tc_list.append(entry)
    theme["tokenColors"] = tc_list

    # UI colors
    colors = OrderedDict()
    for key, ref in VSCODE_UI_COLORS.items():
        colors[key] = resolve_vscode_color(p, ref, variant)
    theme["colors"] = colors

    # Write JSON with tab indentation to match original style
    content = json.dumps(theme, indent="\t", ensure_ascii=False)
    # Add GENERATED comment as first line (JSON doesn't support comments,
    # but VS Code theme files conventionally allow them via jsonc)
    # Actually, the original file has no comment, so we skip it for exact match.
    content += "\n"

    suffix = " Light" if variant == "light" else ""
    filename = f"Low Gravitas Zen{suffix}-color-theme.json"
    path = REPO / "low-gravitas-zen-vscode" / "themes" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  wrote {path.relative_to(REPO)}")
    return path


def generate_intellij_theme(palette, variant):
    """Generate IntelliJ theme JSON file."""
    p = palette
    is_light = variant == "light"
    suffix = "light" if is_light else ""

    theme = OrderedDict()
    theme["name"] = f"Low Gravitas Zen{' Light' if is_light else ''}"
    theme["author"] = "Low Gravitas"
    theme["dark"] = not is_light
    theme["parentTheme"] = "IntelliJ Light" if is_light else "Islands Dark"
    theme["editorScheme"] = f"/low_gravitas_zen{'_light' if is_light else ''}.xml"

    # Resolve colors
    colors = OrderedDict()
    for name, ref in INTELLIJ_THEME_COLORS.items():
        if ref.startswith("#"):
            colors[name] = ref
        elif ref.startswith("@"):
            # palette ref with alpha
            key, alpha = ref[1:].split(":", 1)
            colors[name] = p[key] + alpha
        else:
            # palette key
            colors[name] = p.get(ref, ref)
    theme["colors"] = colors
    theme["ui"] = INTELLIJ_UI
    theme["icons"] = INTELLIJ_ICONS

    content = json.dumps(theme, indent=2, ensure_ascii=False) + "\n"

    filename = f"lowgravitaszen{suffix}.theme.json"
    path = REPO / "intellij" / "resources" / filename
    path.write_text(content)
    print(f"  wrote {path.relative_to(REPO)}")
    return path


def generate_intellij_scheme(palette, variant):
    """Generate IntelliJ color scheme XML file."""
    if INTELLIJ_SCHEME_ATTRS == "BOOTSTRAP_NEEDED":
        print("  SKIP intellij XML — run --bootstrap first")
        return None

    p = palette
    is_light = variant == "light"
    suffix = "_light" if is_light else ""
    parent = "Default" if is_light else "Darcula"
    name = f"Low Gravitas Zen{' Light' if is_light else ''}"

    lines = [
        f'<scheme name="{name}" version="1" parent_scheme="{parent}">',
        '    <metaInfo>',
        '        <property name="created">2024-03-16T18:52:38</property>',
        '        <property name="ide">idea</property>',
        '        <property name="ideVersion">2023.3.5</property>',
        '        <property name="modified">2024-03-16T18:52:38</property>',
        f'        <property name="originalScheme">{name}</property>',
        '    </metaInfo>',
        '    <colors>',
    ]

    for opt_name, ref in INTELLIJ_SCHEME_COLORS.items():
        if ref.startswith("#"):
            val = ref.lstrip("#").upper()
        else:
            val = hex_upper(p[ref])
        lines.append(f'        <option name="{opt_name}" value="{val}" />')

    lines.append('    </colors>')
    lines.append('    <attributes>')

    for attr_name, props in INTELLIJ_SCHEME_ATTRS.items():
        lines.append(f'        <option name="{attr_name}">')
        lines.append('            <value>')
        for prop_name, val in props.items():
            if prop_name in ("FOREGROUND", "BACKGROUND", "EFFECT_COLOR", "ERROR_STRIPE_COLOR"):
                # Try to resolve as palette key
                if val in p:
                    resolved = hex_upper(p[val])
                else:
                    resolved = val  # already hex
            else:
                resolved = val
            lines.append(f'                <option name="{prop_name}" value="{resolved}" />')
        lines.append('            </value>')
        lines.append('        </option>')

    lines.append('    </attributes>')
    lines.append('</scheme>')

    content = "\n".join(lines) + "\n"

    filename = f"low_gravitas_zen{suffix}.xml"
    path = REPO / "intellij" / "resources" / filename
    path.write_text(content)
    print(f"  wrote {path.relative_to(REPO)}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# Bootstrap — extract theme data from existing files
# ══════════════════════════════════════════════════════════════════════════════

def bootstrap_intellij_xml():
    """Read existing IntelliJ XML and output INTELLIJ_SCHEME_ATTRS as Python code."""
    import xml.etree.ElementTree as ET

    xml_path = REPO / "intellij" / "resources" / "low_gravitas_zen.xml"
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Load palette for reverse mapping
    pal = load_palette("dark")
    cmap = {}
    for k, v in pal.items():
        if k.startswith("_"):
            continue
        if isinstance(v, str) and v.startswith("#"):
            cmap[v.lstrip("#").upper()] = k

    attrs = root.find("attributes")
    if attrs is None:
        print("No <attributes> section found")
        return

    print("INTELLIJ_SCHEME_ATTRS = OrderedDict([")
    for option in attrs.findall("option"):
        attr_name = option.get("name")
        value_elem = option.find("value")
        if value_elem is None:
            continue

        props = []
        for prop in value_elem.findall("option"):
            pname = prop.get("name")
            pval = prop.get("value")
            if pname in ("FOREGROUND", "BACKGROUND", "EFFECT_COLOR", "ERROR_STRIPE_COLOR"):
                # Try reverse mapping
                if pval.upper() in cmap:
                    pval_repr = f'"{cmap[pval.upper()]}"'
                else:
                    pval_repr = f'"{pval.upper()}"'
            else:
                pval_repr = f'"{pval}"'
            props.append(f'"{pname}": {pval_repr}')

        props_str = ", ".join(props)
        print(f'    ("{attr_name}", {{{props_str}}}),')
    print("])")


def bootstrap():
    """Run all bootstrap extractors."""
    print("# ── IntelliJ XML attributes ──")
    print()
    bootstrap_intellij_xml()


# ══════════════════════════════════════════════════════════════════════════════
# Check mode
# ══════════════════════════════════════════════════════════════════════════════

def check_mode():
    """Verify generated files match committed versions."""
    import subprocess
    import tempfile
    import shutil

    print("Checking generated files against committed versions...")
    errors = []

    # Generate all dark themes to a temp dir, then compare
    tmpdir = Path(tempfile.mkdtemp())
    try:
        pal = load_palette("dark")

        # Generate all dark themes into temp copies
        # We generate in-place and compare with git, then restore
        # Actually, let's just generate and compare with git show

        # JSON files: compare parsed
        json_checks = [
            ("VS Code dark", "vscode", "dark",
             "low-gravitas-zen-vscode/themes/Low Gravitas Zen-color-theme.json"),
            ("IntelliJ theme", "intellij-theme", "dark",
             "intellij/resources/lowgravitaszen.theme.json"),
        ]

        for label, editor, variant, relpath in json_checks:
            gen_func = EDITORS[editor]
            gen_func(pal, variant)

            filepath = REPO / relpath
            with open(filepath) as f:
                generated = json.load(f)

            result = subprocess.run(
                ["git", "show", f"HEAD:{relpath}"],
                capture_output=True, text=True, cwd=REPO
            )
            if result.returncode != 0:
                print(f"  SKIP {label} (not in git)")
                continue

            committed = json.loads(result.stdout)
            if generated == committed:
                print(f"  OK: {label}")
            else:
                errors.append(f"{label} differs from committed version")

        # XML: compare via parsed structure
        import xml.etree.ElementTree as ET
        generate_intellij_scheme(pal, "dark")
        xml_path = "intellij/resources/low_gravitas_zen.xml"
        gen_tree = ET.parse(REPO / xml_path)
        gen_root = gen_tree.getroot()

        result = subprocess.run(
            ["git", "show", f"HEAD:{xml_path}"],
            capture_output=True, text=True, cwd=REPO
        )
        if result.returncode == 0:
            com_root = ET.fromstring(result.stdout)
            # Compare attributes
            gen_attrs = {}
            for opt in gen_root.find("attributes").findall("option"):
                val = opt.find("value")
                if val is not None:
                    gen_attrs[opt.get("name")] = {
                        p.get("name"): p.get("value") for p in val.findall("option")
                    }
            com_attrs = {}
            for opt in com_root.find("attributes").findall("option"):
                val = opt.find("value")
                if val is not None:
                    com_attrs[opt.get("name")] = {
                        p.get("name"): p.get("value") for p in val.findall("option")
                    }
            if gen_attrs == com_attrs:
                print("  OK: IntelliJ XML scheme")
            else:
                errors.append("IntelliJ XML scheme differs")

        # Text files: compare ignoring GENERATED header
        text_checks = [
            ("Ghostty dark", "ghostty", "dark", "ghostty/LowGravitasZen"),
            ("Warp dark", "warp", "dark", "warp/low_gravitas_zen_theme.yaml"),
        ]

        for label, editor, variant, relpath in text_checks:
            gen_func = EDITORS[editor]
            gen_func(pal, variant)

            filepath = REPO / relpath
            with open(filepath) as f:
                gen_lines = f.readlines()

            result = subprocess.run(
                ["git", "show", f"HEAD:{relpath}"],
                capture_output=True, text=True, cwd=REPO
            )
            if result.returncode != 0:
                print(f"  SKIP {label} (not in git)")
                continue

            com_lines = result.stdout.splitlines(keepends=True)
            # Filter out GENERATED header from both sides
            gen_filtered = [l for l in gen_lines if GENERATED_HEADER_HASH not in l]
            com_filtered = [l for l in com_lines if GENERATED_HEADER_HASH not in l]
            if gen_filtered == com_filtered:
                print(f"  OK: {label}")
            else:
                errors.append(f"{label} differs (ignoring GENERATED header)")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if errors:
        print(f"\n{len(errors)} mismatch(es) found:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nAll checks passed.")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# Light mode seeding
# ══════════════════════════════════════════════════════════════════════════════

def seed_light():
    """Print HSLuv-inverted light palette candidates."""
    pal = load_palette("dark")
    print("# Light mode palette candidates (HSLuv L* inversion)")
    print("# Review and hand-tune before adding to palette.toml [variants.light]")
    print()

    # Invert backgrounds: dark → light
    bg_keys = ["bg_deep", "bg_mid", "bg_raised", "selection", "cursor"]
    for key in bg_keys:
        L, C, H = hex_to_lch(pal[key])
        # Invert lightness: L' = 100 - L, with some warmth preservation
        new_L = min(98, max(85, 100 - L))
        new_hex = lch_to_hex(new_L, C * 0.5, H)  # reduce chroma for light bg
        print(f'{key} = "{new_hex}"  # L*: {L:.1f} → {new_L:.1f}')

    print()

    # ANSI colors: adjust for light backgrounds (increase contrast)
    ansi_keys = [
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
        "bright_black", "bright_red", "bright_green", "bright_yellow",
        "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
    ]
    for key in ansi_keys:
        L, C, H = hex_to_lch(pal[key])
        # For light mode: darken colors to maintain contrast against light bg
        if L > 60:
            new_L = L - 30
        else:
            new_L = L - 10
        new_L = max(15, min(85, new_L))
        new_hex = lch_to_hex(new_L, C, H)
        print(f'{key} = "{new_hex}"  # L*: {L:.1f} → {new_L:.1f}')

    print()
    print("# Terminal selection colors")
    for key in ["terminal_selection_bg", "terminal_selection_fg"]:
        L, C, H = hex_to_lch(pal[key])
        new_L = min(95, max(60, 100 - L))
        new_hex = lch_to_hex(new_L, C * 0.7, H)
        print(f'{key} = "{new_hex}"  # L*: {L:.1f} → {new_L:.1f}')


# ══════════════════════════════════════════════════════════════════════════════
# Standalone CSS
# ══════════════════════════════════════════════════════════════════════════════

def generate_css():
    """Generate docs/low-gravitas-zen.css — standalone color tokens for web."""
    dark_pal = load_palette("dark")
    light_pal = load_palette("light")
    version = dark_pal["_meta"]["version"]

    with open(PALETTE_PATH, "rb") as f:
        data = tomllib.load(f)
    tokens = dict(data.get("tokens", {}))
    tokens_dark = tokens.pop("dark", {})
    tokens_light = tokens.pop("light", {})

    def palette_vars(pal, prefix="lgz"):
        """Emit --lgz-<name>: <hex>; lines for all palette colors."""
        lines = []
        for k, v in pal.items():
            if k.startswith("_") or not isinstance(v, str) or not v.startswith("#"):
                continue
            css_name = k.replace("_", "-")
            lines.append(f"  --{prefix}-{css_name}: {v};")
        return "\n".join(lines)

    def token_vars(token_map, variant_overrides, prefix="lgz"):
        """Emit --<semantic>: var(--lgz-<palette_key>); lines."""
        merged = {**token_map, **variant_overrides}
        lines = []
        for token_name, palette_key in merged.items():
            css_token = token_name.replace("_", "-")
            css_palette = palette_key.replace("_", "-")
            lines.append(f"  --{css_token}: var(--{prefix}-{css_palette});")
        return "\n".join(lines)

    dark_vars = palette_vars(dark_pal)
    light_vars = palette_vars(light_pal)
    dark_token_vars = token_vars(tokens, tokens_dark)
    light_token_vars = token_vars(tokens, tokens_light)

    # The accent token is already in the raw palette with that name,
    # so --accent aliases to --lgz-accent. Same for --error.
    # We add them explicitly so consumers don't have to know.
    extra_dark = [
        "  --accent: var(--lgz-accent);",
        "  --error: var(--lgz-error);",
    ]
    extra_light = [
        "  --accent: var(--lgz-accent);",
        "  --error: var(--lgz-error);",
    ]

    def indent(text, n=2):
        """Add n extra spaces of indentation to each line."""
        prefix = " " * n
        return "\n".join(prefix + line for line in text.split("\n"))

    light_vars_media = indent(light_vars)
    light_token_vars_media = indent(light_token_vars)
    extra_light_media = [indent(l) for l in extra_light]

    css = f"""\
/* Low Gravitas Zen v{version} — CSS Color Tokens
   GENERATED from palette.toml — do not edit by hand.
   https://github.com/low-gravitas/low-gravitas-zen-theme

   Usage:
     <link rel="stylesheet" href="low-gravitas-zen.css">

   Dark mode (default):  just works — :root provides dark palette.
   Light mode:           add data-theme="light" to <html>, or let
                         prefers-color-scheme handle it automatically.
   Manual toggle:        swap data-theme between "dark" and "light".

   Raw palette vars:     --lgz-red, --lgz-bg-deep, --lgz-accent, etc.
   Semantic aliases:     --bg, --surface, --text, --accent, --danger, etc.
*/

/* ── Raw palette (dark — default) ────────────────────────────────────────── */

:root,
[data-theme="dark"] {{
{dark_vars}
}}

/* ── Raw palette (light) ─────────────────────────────────────────────────── */

[data-theme="light"] {{
{light_vars}
}}

@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
{light_vars_media}
  }}
}}

/* ── Semantic aliases (dark — default) ───────────────────────────────────── */

:root,
[data-theme="dark"] {{
{dark_token_vars}
{chr(10).join(extra_dark)}
}}

/* ── Semantic aliases (light) ────────────────────────────────────────────── */

[data-theme="light"] {{
{light_token_vars}
{chr(10).join(extra_light)}
}}

@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
{light_token_vars_media}
{chr(10).join(extra_light_media)}
  }}
}}

/* ── Selection ───────────────────────────────────────────────────────────── */

::selection {{
  background: var(--selection-bg);
  color: var(--selection-fg);
}}
"""

    docs_dir = REPO / "docs"
    docs_dir.mkdir(exist_ok=True)
    path = docs_dir / "low-gravitas-zen.css"
    path.write_text(css)
    print(f"  wrote {path.relative_to(REPO)}")
    return path
# ══════════════════════════════════════════════════════════════════════════════
# Demo site
# ══════════════════════════════════════════════════════════════════════════════

def generate_site():
    """Generate docs/index.html from site/ templates + colorized code samples."""
    import re as _re
    import shutil

    dark_pal = load_palette("dark")
    try:
        light_pal = load_palette("light")
    except Exception:
        light_pal = dark_pal

    version = dark_pal["_meta"]["version"]

    # ── Token-based colorizer ────────────────────────────────────────────

    _TOK_PATTERN = _re.compile(
        r'("""[\s\S]*?"""|'
        r"'''[\s\S]*?'''|"
        r'f"[^"]*?"|"[^"]*?"|'
        r"f'[^']*?'|'[^']*?'|"
        r'`[^`]*?`|'
        r'//[^\n]*|/\*[\s\S]*?\*/|'
        r'#[^\n]*|'
        r'\b\d+\.?\d*\b|'
        r'\b[A-Za-z_$]\w*\b|'
        r'=>|'
        r'\S)'
    )

    def _tokenize(code, keywords, builtins=None, track_def=False):
        builtins = builtins or set()
        prev_was_def = False
        for m in _TOK_PATTERN.finditer(code):
            t = m.group()
            if t.startswith(("#",)):
                yield ("tk-comment", t)
            elif t.startswith(("//",)):
                yield ("tk-comment", t)
            elif t.startswith(("/*",)):
                yield ("tk-comment", t)
            elif t.startswith(('"""', "'''", '"', "'", 'f"', "f'", "`")):
                yield ("tk-string", t)
            elif _re.fullmatch(r'\d+\.?\d*', t):
                yield ("tk-number", t)
            elif t in keywords:
                yield ("tk-keyword", t)
                prev_was_def = track_def and t == "def"
                continue
            elif prev_was_def:
                yield ("tk-function", t)
            elif t in builtins:
                yield ("tk-type", t)
            else:
                yield (None, t)
            prev_was_def = False

    def _esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _tokens_to_html(code, tokenizer_args):
        keywords, builtins, track_def = tokenizer_args
        tokens = list(_tokenize(code, keywords, builtins, track_def))
        parts = []
        pos = 0
        tok_iter = iter(tokens)
        for m in _TOK_PATTERN.finditer(code):
            if m.start() > pos:
                parts.append(_esc(code[pos:m.start()]))
            try:
                cls, text = next(tok_iter)
            except StopIteration:
                parts.append(_esc(m.group()))
                pos = m.end()
                continue
            escaped = _esc(text)
            if cls:
                parts.append(f'<span class="{cls}">{escaped}</span>')
            else:
                parts.append(escaped)
            pos = m.end()
        if pos < len(code):
            parts.append(_esc(code[pos:]))
        return "".join(parts)

    PY_KW = {"def","return","if","elif","else","for","in","import","from","class",
             "try","except","as","with","async","await","not","and","or","is",
             "True","False","None","while","yield","raise","pass","break","continue","lambda"}
    PY_BUILTIN = {"print","range","len","int","list","str","bool","dict","set","tuple",
                   "type","isinstance","super","enumerate","zip","map","filter","sorted","open"}
    JS_KW = {"const","let","var","function","async","await","try","catch","throw","return",
             "if","else","new","typeof","null","undefined","true","false","this","class",
             "import","export","from","of","in","for","while","switch","case","break","default","do","yield"}

    def colorize_python(code):
        return _tokens_to_html(code, (PY_KW, PY_BUILTIN, True))

    def colorize_js(code):
        return _tokens_to_html(code, (JS_KW, set(), False))

    def _add_line_numbers(html_code):
        lines = html_code.split("\n")
        return "\n".join(
            f'<span><span class="line-num">{i:>2}</span>{line}</span>'
            for i, line in enumerate(lines, 1)
        )

    def _add_selection_and_cursor(html_code):
        lines = html_code.split("\n")
        result = []
        for i, line in enumerate(lines, 1):
            cls = ""
            content = line
            if i == 12:
                cls = ' class="cursor-line"'
                content += '<span class="cursor-bar"></span>'
            if i == 6:
                content = content.replace(
                    '<span class="tk-type">range</span>(<span class="tk-number">2</span>, n)',
                    '<span class="selected-text"><span class="tk-type">range</span>(<span class="tk-number">2</span>, n)</span>'
                )
            result.append(f'<span{cls}><span class="line-num">{i:>2}</span>{content}</span>')
        return "\n".join(result)

    def _label_color_for_swatch(swatch_hex):
        r, g, b = hex_to_rgb(swatch_hex)
        def lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
        cr_white = 1.05 / (lum + 0.05)
        cr_black = (lum + 0.05) / 0.05
        return "#ffffff" if cr_white > cr_black else "#000000"

    # ── Code samples ─────────────────────────────────────────────────────

    python_sample = (
        'def fibonacci(n: int) -> list[int]:\n'
        '    """Generate Fibonacci sequence up to n terms."""\n'
        '    if n <= 0:\n'
        '        return []\n'
        '    sequence = [0, 1]\n'
        '    for i in range(2, n):\n'
        '        sequence.append(sequence[-1] + sequence[-2])\n'
        '    return sequence[:n]\n'
        '\n'
        '# Print the first 10 Fibonacci numbers\n'
        'result = fibonacci(10)\n'
        'print(f"Fibonacci: {result}")'
    )

    js_sample = (
        'const fetchUserData = async (userId) => {\n'
        '  try {\n'
        '    const response = await fetch(`/api/users/${userId}`);\n'
        '    if (!response.ok) {\n'
        '      throw new Error(`HTTP ${response.status}`);\n'
        '    }\n'
        '    const { name, email, role } = await response.json();\n'
        '    return { name, email, role, active: true };\n'
        '  } catch (error) {\n'
        '    console.error("Failed to fetch user:", error);\n'
        '    return null;\n'
        '  }\n'
        '};'
    )

    # ── Generate swatches ────────────────────────────────────────────────

    swatch_names = [
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
        "bright-black", "bright-red", "bright-green", "bright-yellow",
        "bright-blue", "bright-magenta", "bright-cyan", "bright-white",
        "bg-deep", "bg-mid", "bg-raised", "selection", "cursor", "accent",
    ]
    swatch_lines = []
    for name in swatch_names:
        pal_key = name.replace("-", "_")
        dark_hex = dark_pal.get(pal_key, "#888888")
        light_hex = light_pal.get(pal_key, dark_hex)
        dark_label = _label_color_for_swatch(dark_hex)
        light_label = _label_color_for_swatch(light_hex)
        swatch_lines.append(
            f'<div class="swatch" style="background: var(--lgz-{name}); '
            f'--label-dark: {dark_label}; --label-light: {light_label};" '
            f'data-dark="{dark_hex}" data-light="{light_hex}">'
            f'<span>{name}</span></div>'
        )

    # ── Assemble from templates ──────────────────────────────────────────

    python_html = _add_selection_and_cursor(colorize_python(python_sample))
    js_html = _add_line_numbers(colorize_js(js_sample))

    template = (REPO / "site" / "site.html").read_text()
    html = (template
        .replace("{{swatches}}", "\n".join(swatch_lines))
        .replace("{{python_code}}", python_html)
        .replace("{{js_code}}", js_html)
        .replace("{{version}}", version)
    )

    docs_dir = REPO / "docs"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "index.html").write_text(html)
    print(f"  wrote docs/index.html")

    shutil.copy2(REPO / "site" / "site.css", docs_dir / "site.css")
    print(f"  wrote docs/site.css")

    return docs_dir / "index.html"




# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

EDITORS = {
    "ghostty": generate_ghostty,
    "warp": generate_warp,
    "iterm": generate_iterm,
    "vscode": generate_vscode,
    "intellij-theme": generate_intellij_theme,
    "intellij-scheme": generate_intellij_scheme,
}


def main():
    parser = argparse.ArgumentParser(description="Generate Low Gravitas Zen themes")
    parser.add_argument("--variant", choices=["dark", "light", "all"], default="all",
                        help="Which variant to generate (default: all)")
    parser.add_argument("--editor", choices=list(EDITORS.keys()) + ["all", "intellij"],
                        default="all", help="Which editor to generate (default: all)")
    parser.add_argument("--check", action="store_true",
                        help="Verify generated files match committed versions")
    parser.add_argument("--seed-light", action="store_true",
                        help="Print HSLuv-inverted light palette candidates")
    parser.add_argument("--bootstrap", action="store_true",
                        help="Extract theme data from existing files (dev tool)")
    parser.add_argument("--site", action="store_true",
                        help="Generate demo site at docs/index.html")
    args = parser.parse_args()

    if args.bootstrap:
        bootstrap()
        return 0

    if args.seed_light:
        seed_light()
        return 0

    if args.check:
        return check_mode()

    if args.site:
        generate_site()
        generate_css()
        return 0

    variants = ["dark", "light"] if args.variant == "all" else [args.variant]

    # Resolve editor list
    if args.editor == "all":
        editor_keys = list(EDITORS.keys())
    elif args.editor == "intellij":
        editor_keys = ["intellij-theme", "intellij-scheme"]
    else:
        editor_keys = [args.editor]

    for variant in variants:
        print(f"\n{'='*60}")
        print(f"Generating {variant} variant")
        print(f"{'='*60}")
        pal = load_palette(variant)

        for editor_key in editor_keys:
            gen_func = EDITORS[editor_key]
            gen_func(pal, variant)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

#!/usr/bin/env python3
"""Build the profile hero cards (desktop + mobile, dark + light).

Layout, grid, palette and tone curve are copied from the reference profile
(LahsenAitOiahmane): 1120x650 desktop card, 480-wide mobile card, a 57x76
binary-glyph portrait on a 5.3 x 6.4 grid, right-aligned values on the
desktop card, stacked values on the mobile card.

The portrait glyphs come from assets/portrait-<theme>.json (built by
build-portrait.py from a photo); if that file is missing they are read back
out of the existing SVG asset.

Usage:  python3 build-hero.py
"""
import json
import re
from pathlib import Path

ASSETS = Path(__file__).parent / 'assets'

# ---------------------------------------------------------------- content
PROMPT = 'evm0x@localhost:~$ ./whoami'
GROUPS = [
    [('Role:', 'Web3 dev / bot engineer / AI agent builder'),
     ('Focus:', 'Autonomous agents / onchain apps / trading bots'),
     ('Shipped:', 'Squeek Pack / splitmon / poker-bot'),
     ('Next:', 'Arena Kuru / THE SNIPER')],
    [('Languages.Code:', 'Python / TypeScript / Solidity / Bash'),
     ('Languages.LowLevel:', 'EVM bytecode / calldata decoding'),
     ('Tools.Chain:', 'Foundry / Hardhat / ethers / web3.py'),
     ('Tools.Bot:', 'Python async / Playwright / Telegram')],
    [('Agents.LLM:', '[OI] / Anthropic / Ollama / local models'),
     ('Agents.Framework:', 'LangChain / MCP / custom agent loops'),
     ('Agents.Protocol:', 'MCP servers / x402 / ERC-8004'),
     ('Agents.Runtime:', 'systemd / Docker / cron / tailscale')],
    [('Platforms:', 'EVM / BSC / Base / Monad / Solana'),
     ('Practice:', 'live agents / small size / real fills'),
     ('Notes:', 'KTL DAO / agents &amp; writeups')],
    [('GitHub.Public:', '31 public repos / 35 stars'),
     ('GitHub.Checked:', '2026-11-16 UTC')],
]
FOOTER = 'Every block is a clue.'
META_LEFT = 'EVM0x :: terminal alter ego'
META_RIGHT = '45 / 69 / 01000101'

THEMES = {
    'dark': dict(bg='#000000', stroke='#25370d', accent='#b4ff57',
                 value='#eeeeee', meta='#969696'),
    'light': dict(bg='#ffffff', stroke='#cddbb7', accent='#548000',
                  value='#1e1e1e', meta='#666666'),
}

# ---------------------------------------------------------------- geometry
DESK_W, DESK_H = 1120, 650
ROW_X, ROW_RIGHT = 393, 1097
ROW_TOP, ROW_STEP, GROUP_GAP = 91, 22, 42
CHAR = 0.6038           # Roboto Mono advance width in em
MONO = 'Roboto Mono, Liberation Mono, Courier New, monospace'

MOB_W = 480
MOB_X = 24
MOB_WRAP = 43           # characters per line at 16.5px in a 480px card

GLYPH = re.compile(
    r'<text x="([\d.]+)" y="([\d.]+)" fill="(#[0-9a-fA-F]{6})" '
    r'font-size="([\d.]+)" font-weight="600">([01])</text>')


def portrait(path, theme):
    """Pull the portrait glyphs out of a JSON grid, or back out of an asset."""
    grid = ASSETS / ('portrait-%s.json' % theme)
    if grid.exists():
        cells = json.loads(grid.read_text())
        return [(str(c['x']), str(c['y']), c['fill'], str(c['size']), c['ch'])
                for c in cells]
    s = path.read_text()
    st = s.find('<g id="binary-portrait"')
    end = s.find('</g>\n</g>', st)
    return GLYPH.findall(s[st:end])


def portrait_svg(glyphs):
    out = ['<g id="binary-portrait" aria-hidden="true">']
    for x, y, fill, size, ch in glyphs:
        out.append('<text x="%s" y="%s" fill="%s" font-size="%s" '
                   'font-weight="600">%s</text>' % (x, y, fill, size, ch))
    out.append('</g>')
    return '\n'.join(out)


def wrap(text, width):
    """Wrap a value on ' / ' boundaries so it never overflows the mobile card."""
    if len(text) <= width:
        return [text]
    parts, lines, cur = text.split(' / '), [], ''
    for i, p in enumerate(parts):
        piece = p + (' / ' if i < len(parts) - 1 else '')
        if cur and len(cur) + len(piece.rstrip()) > width:
            lines.append(cur.rstrip())
            cur = piece
        else:
            cur += piece
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def head(title, desc, w, h, t):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img" aria-labelledby="title desc">\n'
            '<title id="title">%s</title>\n<desc id="desc">%s</desc>\n'
            "<style>\ntext{font-family:'Roboto Mono','Liberation Mono',"
            "'Courier New',monospace;white-space:pre}\n</style>\n"
            '<rect x=".5" y=".5" width="%d" height="%d" rx="12" fill="%s" '
            'stroke="%s"/>\n' % (w, h, w, h, title, desc, w - 1, h - 1, t['bg'], t['stroke']))


def desc_text():
    fields = '; '.join('%s %s' % (l.rstrip(':'), v)
                       for g in GROUPS for l, v in g)
    return ('A %s terminal card. A binary-rain portrait built from 3036 zero and '
            'one characters in a grey ramp, next to a lime prompt %s followed by a '
            'dotted field list: %s. Footer: %s'
            % ('black', PROMPT, fields, FOOTER))


def desktop(glyphs, theme):
    t = THEMES[theme]
    desc = desc_text().replace('A black', 'A white') if theme == 'light' else desc_text()
    desc = desc.replace('lime prompt', 'olive prompt') if theme == 'light' else desc
    o = [head('EVM0x / terminal alter ego', desc, DESK_W, DESK_H, t)]
    o.append('<g transform="translate(23 34)">')
    o.append(portrait_svg(glyphs))
    o.append('</g>')
    o.append('<text x="%d" y="42" fill="%s" font-size="17" font-weight="700">%s</text>'
             % (ROW_X, t['accent'], PROMPT))
    o.append('<text x="%.1f" y="42" fill="%s" font-size="17" font-weight="700" '
             'class="cursor">_</text>' % (ROW_X + len(PROMPT) * 17 * CHAR, t['accent']))
    o.append('<path d="M%d 61h704" stroke="%s" stroke-dasharray="2 5"/>'
             % (ROW_X, t['stroke']))
    y = ROW_TOP
    for gi, group in enumerate(GROUPS):
        for label, value in group:
            start = ROW_X + (len(label) * 15 * CHAR) + 12
            end = ROW_RIGHT - (len(value.replace('&amp;', '&')) * 15 * CHAR) - 8
            if end - start > 20:
                o.append('<path d="M%.1f %dH%.1f" stroke="%s" stroke-dasharray="2 5"/>'
                         % (start, y - 4, end, t['stroke']))
            o.append('<text x="%d" y="%d" fill="%s" font-size="15" font-weight="400">%s</text>'
                     % (ROW_X, y, t['accent'], label))
            o.append('<text x="%d" y="%d" fill="%s" font-size="15" font-weight="400" '
                     'text-anchor="end">%s</text>' % (ROW_RIGHT, y, t['value'], value))
            y += ROW_STEP
        y += GROUP_GAP - ROW_STEP
        if gi == len(GROUPS) - 2:
            o.append('<path d="M%d %dh704" stroke="%s" stroke-dasharray="2 5"/>'
                     % (ROW_X, y - 4, t['stroke']))
            y += 27
    o.append('<text x="%d" y="583" fill="%s" font-size="19" font-weight="700">%s</text>'
             % (ROW_X, t['accent'], FOOTER))
    o.append('<text x="24" y="620" fill="%s" font-size="12" font-weight="400">%s</text>'
             % (t['meta'], META_LEFT))
    o.append('<text x="%d" y="620" fill="%s" font-size="12" font-weight="400" '
             'text-anchor="end">%s</text>' % (ROW_RIGHT, t['meta'], META_RIGHT))
    o.append('</svg>')
    return '\n'.join(o) + '\n'


def mobile(glyphs, theme):
    t = THEMES[theme]
    desc = desc_text().replace('A black', 'A white') if theme == 'light' else desc_text()
    desc = desc.replace('lime prompt', 'olive prompt') if theme == 'light' else desc

    # measure first so the card is exactly as tall as the content
    rows, y = [], 558
    for gi, group in enumerate(GROUPS):
        for label, value in group:
            lines = wrap(value.replace('&amp;', '&'), MOB_WRAP)
            rows.append((y, label, lines))
            y += 24 + 24 * len(lines) - 24
            y += 34
        y += 48 - 34
        if gi == len(GROUPS) - 2:
            y += 27
    footer_y, checked_y = y + 22, y + 22 + 35
    height = checked_y + 47

    o = [head('EVM0x / terminal alter ego (mobile)', desc, MOB_W, height, t)]
    o.append('<g transform="translate(23 34)">')
    o.append(portrait_svg(glyphs))
    o.append('</g>')
    o.append('<text x="%d" y="44" fill="%s" font-size="16" font-weight="700">%s</text>'
             % (MOB_X, t['accent'], PROMPT))
    o.append('<text x="%d" y="507" fill="%s" font-size="14" font-weight="400" '
             'text-anchor="end">%s</text>' % (MOB_W - MOB_X, t['meta'], META_RIGHT))
    for y, label, lines in rows:
        o.append('<text x="%d" y="%d" fill="%s" font-size="16" font-weight="400">%s</text>'
                 % (MOB_X, y, t['accent'], label))
        for i, line in enumerate(lines):
            o.append('<text x="%d" y="%d" fill="%s" font-size="16.5" font-weight="400">%s</text>'
                     % (MOB_X, y + 24 + 24 * i, t['value'], line.replace('&', '&amp;')))
    o.append('<text x="%d" y="%d" fill="%s" font-size="18" font-weight="700">%s</text>'
             % (MOB_X, footer_y, t['accent'], FOOTER))
    o.append('<text x="%d" y="%d" fill="%s" font-size="11" font-weight="400">'
             'GitHub checked 2026-11-16 UTC</text>' % (MOB_X, checked_y, t['meta']))
    o.append('</svg>')
    return '\n'.join(o) + '\n'


if __name__ == '__main__':
    for theme, name in (('dark', 'hero-dark.svg'), ('light', 'hero-light.svg')):
        g = portrait(ASSETS / name, theme)
        assert len(g) == 3036, '%s: expected 3036 glyphs, got %d' % (name, len(g))
        (ASSETS / name).write_text(desktop(g, theme))
        (ASSETS / ('hero-%s-mobile.svg' % theme)).write_text(mobile(g, theme))
        print('%s: %d glyphs -> desktop + mobile' % (theme, len(g)))

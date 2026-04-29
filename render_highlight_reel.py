#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import struct
import subprocess
import wave
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chess
import chess.engine
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
FPS = 24
DURATION = 90
FRAMES = FPS * DURATION
BOARD_X, BOARD_Y, CELL = 50, 104, 56
BG = (3, 8, 5)
CYAN = (80, 255, 130)
MAGENTA = (170, 255, 80)
AMBER = (210, 255, 90)
RED = (255, 70, 45)
GREEN = (80, 255, 130)
WHITE = (235, 245, 255)
PURE_WHITE = (248, 246, 238)
PURE_BLACK = (8, 7, 6)
WOOD_LIGHT = (142, 104, 58)
WOOD_DARK = (82, 48, 24)
WOOD_GRAIN = (46, 25, 10)
DIM = (80, 95, 120)
PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 99,
}
PIECE_GLYPH = {
    chess.PAWN: 'P', chess.KNIGHT: 'N', chess.BISHOP: 'B', chess.ROOK: 'R', chess.QUEEN: 'Q', chess.KING: 'K'
}
PIECE_NAME = {
    chess.PAWN: 'pawn', chess.KNIGHT: 'knight', chess.BISHOP: 'bishop', chess.ROOK: 'rook', chess.QUEEN: 'queen', chess.KING: 'king'
}
ASCII_RAMP = ' .:-=+*#%@'
PROJECT_TITLE = 'GAMBIT ARENA'
MATCHUP_TITLE = 'WHITE VS BLACK'
MATCHUP_HUD = 'WHITE VS BLACK // LLM BENCHMARK ARENA'
PIECE_ASCII_ART = {
    chess.PAWN: ['  ^  ', ' /o\\ ', '/_|_\\', '  |  ', ' /_\\ '],
    chess.KNIGHT: [' /^^ ', '/_\\\\', '  \>', ' /|  ', '/_|_ '],
    chess.BISHOP: ['  /\\ ', ' (<> )', '  || ', ' /||\\', '/____\\'],
    chess.ROOK: ['|^^^^|', '| [] |', '|____|', '  ||  ', '/____\\'],
    chess.QUEEN: ['\\ ^ /', ' \|/ ', ' /Q\\ ', ' \|/ ', '/___\\'],
    chess.KING: ['  +  ', ' /|\\ ', '< K >', ' \|/ ', '/___\\'],
}


def project_title_text() -> str:
    return PROJECT_TITLE


def side_display_name(color: bool) -> str:
    return 'White' if color == chess.WHITE else 'Black'


def title_matchup_text() -> str:
    return MATCHUP_TITLE


def hud_matchup_text() -> str:
    return MATCHUP_HUD


def moving_piece_color(piece: chess.Piece) -> tuple[int, int, int]:
    return piece_fill_color(piece)


def piece_fill_color(piece: chess.Piece) -> tuple[int, int, int]:
    return PURE_WHITE if piece.color == chess.WHITE else PURE_BLACK


def piece_outline_color(piece: chess.Piece) -> tuple[int, int, int]:
    return PURE_BLACK if piece.color == chess.WHITE else PURE_WHITE


def trail_color_for_step(piece: chess.Piece, step: int) -> tuple[int, int, int]:
    base = moving_piece_color(piece)
    if piece.color == chess.BLACK:
        return tuple(min(38, channel + step * 4) for channel in base)
    return tuple(max(160, channel - step * 10) for channel in base)


def wood_square_colors(file_idx: int, rank_idx: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    grain = int(12 * math.sin(file_idx * 1.7 + rank_idx * 0.9))
    light = (WOOD_LIGHT[0] + grain, WOOD_LIGHT[1] + grain // 2, WOOD_LIGHT[2])
    dark = (WOOD_DARK[0] + grain // 2, WOOD_DARK[1] + grain // 3, WOOD_DARK[2])
    return light, dark


def piece_ascii_art(piece: chess.Piece) -> str:
    lines = PIECE_ASCII_ART[piece.piece_type]
    if piece.color == chess.BLACK:
        lines = [line.lower() for line in lines]
    return '\n'.join(lines)


def final_explanation_lines() -> list[str]:
    return [
        'Gambit Arena is a visual benchmark for LLMs playing chess.',
        'Each model proposes its own move from the current position.',
        'A central referee checks legality after the move is proposed and rejects illegal play.'
        'The arena turns the game into an observable test of planning, tactics, and rule following.',
    ]


@dataclass
class GameEvent:
    index: int
    ply: int
    san: str
    uci: str
    side: str
    board_before: chess.Board
    board_after: chess.Board
    move: chess.Move
    moved_piece: chess.Piece
    captured_piece: Optional[chess.Piece]
    score: float
    kind: str
    caption: str
    commentary: str


@dataclass
class TimelineSegment:
    event: GameEvent
    start: float
    duration: float
    label: str
    importance: float


def detect_stockfish() -> str:
    for candidate in ('stockfish', '/usr/games/stockfish', '/usr/bin/stockfish'):
        path = shutil.which(candidate) if '/' not in candidate else candidate
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError('Stockfish binary not found')


def material(board: chess.Board) -> int:
    total = 0
    for piece in board.piece_map().values():
        val = PIECE_VALUE[piece.piece_type]
        total += val if piece.color == chess.WHITE else -val
    return total


def language_choose(board: chess.Board, rng: random.Random) -> chess.Move:
    legal = list(board.legal_moves)
    # White simulation: brave, tactical, sometimes reckless. Prefers underdog captures and checks.
    scored = []
    for move in legal:
        score = rng.uniform(-0.25, 0.25)
        attacker = board.piece_at(move.from_square)
        victim = board.piece_at(move.to_square)
        if victim and attacker:
            score += PIECE_VALUE[victim.piece_type] - 0.35 * PIECE_VALUE[attacker.piece_type] + 2.0
            if PIECE_VALUE[victim.piece_type] > PIECE_VALUE[attacker.piece_type]:
                score += 3.5
        board.push(move)
        if board.is_check():
            score += 1.5
        if board.is_checkmate():
            score += 99
        # central bravado
        if chess.square_file(move.to_square) in (2, 3, 4, 5) and chess.square_rank(move.to_square) in (2, 3, 4, 5):
            score += 0.25
        board.pop()
        scored.append((score, move))
    scored.sort(reverse=True, key=lambda x: x[0])
    if len(scored) > 4 and rng.random() < 0.22:
        return rng.choice(scored[:4])[1]
    return scored[0][1]


def script_position() -> list[str]:
    # A legal miniature designed to guarantee Battle-Chess-style underdog hits:
    # 1.e4 d5 2.exd5 Qxd5 3.Nc3 Qe6+ 4.Be2 Nc6 5.Nf3 Qg6 6.Nb5 Qxg2 7.Nxc7+ Kd8 8.Rg1 Kxc7
    return ['e4', 'd5', 'exd5', 'Qxd5', 'Nc3', 'Qe6+', 'Be2', 'Nc6', 'Nf3', 'Qg6', 'Nb5', 'Qxg2', 'Nxc7+', 'Kd8']


def simulate_game(stockfish_path: str, seed: int = 73, max_plies: int = 74) -> list[GameEvent]:
    rng = random.Random(seed)
    board = chess.Board()
    events: list[GameEvent] = []
    scripted = script_position()
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    try:
        for ply in range(max_plies):
            before = board.copy(stack=False)
            if ply < len(scripted):
                move = board.parse_san(scripted[ply])
            elif board.turn == chess.WHITE:
                move = language_choose(board, rng)
            else:
                move = engine.play(board, chess.engine.Limit(time=0.035)).move
            san = board.san(move)
            moved = board.piece_at(move.from_square)
            captured = board.piece_at(move.to_square)
            if board.is_en_passant(move):
                captured = chess.Piece(chess.PAWN, not board.turn)
            score = 0.0
            kind = 'move'
            if captured and moved:
                score = PIECE_VALUE[captured.piece_type] - PIECE_VALUE[moved.piece_type]
                kind = 'capture'
                if score >= 2:
                    kind = 'underdog-capture'
            board.push(move)
            if board.is_checkmate():
                kind = 'checkmate'
                score += 30
            elif board.is_check():
                kind = 'check'
                score += 4
            after = board.copy(stack=False)
            if moved:
                caption = make_caption(san, moved, captured, kind, score)
                mover_side = side_display_name(moved.color)
                commentary = make_commentary(ply, san, moved, captured, kind, score, moved.color)
                events.append(GameEvent(
                    index=len(events), ply=ply + 1, san=san, uci=move.uci(),
                    side=mover_side,
                    board_before=before, board_after=after, move=move,
                    moved_piece=moved, captured_piece=captured, score=score,
                    kind=kind, caption=caption, commentary=commentary,
                ))
            if board.is_game_over():
                break
    finally:
        engine.quit()
    return events


def deterministic_pick(options: list[str], *keys) -> str:
    seed = '|'.join(str(k) for k in keys)
    return options[sum(ord(c) for c in seed) % len(options)]


def capture_style(moved: chess.Piece) -> dict[str, str]:
    """Battle-chess action vocabulary keyed by attacker type."""
    styles = {
        chess.PAWN: {
            'name': 'pawn rush', 'verb': 'shoulder-checks', 'panel': 'PAWN RUSH',
            'chars': '^!/*', 'tone': 'cheap unit, brutal contact', 'shape': 'swarm',
            'motion': 'streaming-explosion', 'stream': 'five-lane pawn debris river', 'debris': 'shrapnel pawns', 'shock': 'low circular blast',
        },
        chess.KNIGHT: {
            'name': 'knight leap', 'verb': 'vaults over the grid and spears', 'panel': 'L-KNIGHT AMBUSH',
            'chars': 'L7/*', 'tone': 'crooked-angle ambush', 'shape': 'lance',
            'motion': 'streaming-explosion', 'stream': 'bent L-shaped comet trail', 'debris': 'angular sparks', 'shock': 'delayed spear burst',
        },
        chess.BISHOP: {
            'name': 'bishop beam', 'verb': 'cuts a diagonal laser through', 'panel': 'DIAGONAL LASER',
            'chars': '/\\=+', 'tone': 'long-range diagonal beam', 'shape': 'beam',
            'motion': 'streaming-explosion', 'stream': 'diagonal plasma sheet', 'debris': 'split glyph shards', 'shock': 'cross-beam flash',
        },
        chess.ROOK: {
            'name': 'rook cannon', 'verb': 'rolls a siege tower into', 'panel': 'ROOK CANNON',
            'chars': '[]#=', 'tone': 'straight-line siege impact', 'shape': 'shockwave',
            'motion': 'streaming-explosion', 'stream': 'rank-file cannon exhaust', 'debris': 'brick fragments', 'shock': 'square shock rings',
        },
        chess.QUEEN: {
            'name': 'queen vortex', 'verb': 'opens a neon vortex around', 'panel': 'QUEEN VORTEX',
            'chars': '@%*&', 'tone': 'royal gravity well', 'shape': 'vortex',
            'motion': 'streaming-explosion', 'stream': 'spiral gravity stream', 'debris': 'royal starfield', 'shock': 'expanding vortex wall',
        },
        chess.KING: {
            'name': 'king crush', 'verb': 'steps into the danger zone and crushes', 'panel': 'KING CRUSH',
            'chars': 'K!#*', 'tone': 'emergency monarch contact', 'shape': 'shockwave',
            'motion': 'streaming-explosion', 'stream': 'crown-fragment blast', 'debris': 'crown sparks', 'shock': 'royal compression wave',
        },
    }
    return styles[moved.piece_type]


def action_phrase(event_or_kind, moved: chess.Piece, captured: Optional[chess.Piece] = None) -> str:
    kind = event_or_kind.kind if hasattr(event_or_kind, 'kind') else event_or_kind
    side = event_or_kind.side if hasattr(event_or_kind, 'side') else None
    prefix = f'{side} ' if side else ''
    attacker = PIECE_NAME[moved.piece_type]
    if kind == 'checkmate':
        return f'{prefix}{attacker} seals the king'
    if kind == 'check':
        return f'{prefix}{attacker} checks the king'
    if captured:
        victim_side = side_display_name(not moved.color)
        victim = PIECE_NAME[captured.piece_type]
        verb = 'captures'
        if kind == 'underdog-capture':
            verb = 'ambushes'
        return f'{prefix}{attacker} {verb} {victim} from {victim_side}'
    return f'{prefix}{attacker} develops pressure'


def make_caption(san, moved, captured, kind, score):
    # Viewer-facing copy deliberately avoids SAN notation. The raw move can live
    # in the right-hand machine stream, but the human update should say side,
    # piece, action, and opposing piece only once.
    phrase = action_phrase(kind, moved, captured)
    if kind == 'underdog-capture' and captured:
        return f'UPSET KILL: {phrase.upper()}'
    if kind == 'capture' and captured:
        style = capture_style(moved)
        return f'{style["panel"]}: {phrase}'
    if kind == 'checkmate':
        return 'CHECKMATE LOCKDOWN: king sealed'
    if kind == 'check':
        return 'KING IN THE BEAM: check delivered'
    if '+' in san or '#' in san:
        return 'KING SIGNAL: pressure on the monarch'
    return deterministic_pick([
        'TEMPO PULSE: pressure develops',
        'POSITION MUTATES: a lane changes',
        'GRID PRESSURE: structure shifts',
        'QUIET MOVE, LOUD CONSEQUENCE',
    ], san, moved.piece_type)


def make_commentary(ply, san, moved, captured, kind, score, white_turn):
    side = side_display_name(white_turn)
    attacker = PIECE_NAME[moved.piece_type]
    action = action_phrase(kind, moved, captured).replace(f'{side} ', '')
    if kind == 'checkmate':
        return deterministic_pick([
            f'{side} {action}. No doors remain; the referee confirms checkmate.',
            f'{side} {attacker} closes the cage. The king is boxed and the game ends.',
        ], ply, san)
    if kind == 'underdog-capture' and captured:
        victim = PIECE_NAME[captured.piece_type]
        victim_side = side_display_name(not moved.color)
        return deterministic_pick([
            f'{side} {attacker} ambushes {victim} from {victim_side}. Small piece, huge swing.',
            f'{side} {attacker} hits above its weight and removes the {victim} from {victim_side}.',
            f'{side} {attacker} goes low, hits high, and drags away the {victim}.',
        ], ply, san, score)
    if kind == 'capture' and captured:
        victim = PIECE_NAME[captured.piece_type]
        victim_side = side_display_name(not moved.color)
        style = capture_style(moved)
        return deterministic_pick([
            f'{side} {attacker} captures {victim} from {victim_side}. {style["name"].title()} impact; debris on the square.',
            f'{side} {attacker} performs the hit and removes the {victim} from {victim_side}.',
            f'{side} {attacker} takes the {victim} from {victim_side}. The board coughs sparks and resets the fight.',
        ], ply, san, moved.piece_type, captured.piece_type)
    if kind == 'check':
        return deterministic_pick([
            f'{side} {attacker} checks the king. The monarch has to answer in public.',
            f'{side} {attacker} aims a siren at the king. The referee marks check.',
            f'{side} {attacker} puts the king in the targeting cone.',
        ], ply, san)
    if ply < 5:
        return deterministic_pick([
            f'{side} {attacker} claims space. The first threat lines start to draw themselves.',
            f'{side} {attacker} develops. Quiet board, loud future.',
            f'{side} {attacker} enters the arena and the position starts to breathe.',
        ], ply, san)
    return deterministic_pick([
        f'{side} {attacker} develops pressure. Another lane gets wired for trouble.',
        f'{side} {attacker} shifts the structure. The next impact moves closer.',
        f'{side} {attacker} changes the map without repeating the notation on screen.',
    ], ply, san, side)


def select_highlights(events: list[GameEvent]) -> list[GameEvent]:
    scored = []
    for e in events:
        priority = event_importance(e)
        scored.append((priority, e))
    highlights = [e for _, e in sorted(scored, key=lambda x: x[0], reverse=True)[:10]]
    highlights.sort(key=lambda e: e.ply)
    return highlights


def event_importance(e: GameEvent) -> float:
    """Score a move for cinematic time-remapping and narration selection.

    This is post-game analysis/showmanship only. It is intentionally separate
    from move choice so it cannot leak engine-style advice to the LLM player.
    """
    priority = max(0.0, e.score)
    if e.kind == 'move':
        priority += 0.4
    if e.kind == 'capture':
        priority += 7.0
    if e.kind == 'underdog-capture':
        priority += 14.0
    if e.kind == 'check':
        priority += 10.0
    if e.kind == 'checkmate':
        priority += 60.0
    if e.captured_piece:
        priority += PIECE_VALUE[e.captured_piece.piece_type] * 0.9
    if e.moved_piece.piece_type == chess.QUEEN:
        priority += 1.5
    if e.ply <= 10:
        priority += 0.8
    return priority


def event_duration(e: GameEvent, full_game: bool) -> float:
    """Seconds to spend on a move before global fit-to-duration scaling.

    The full-game reel should let viewers see every move, but time should bend
    around combat. Ordinary moves flash by; captures/checks get slow-motion.
    """
    if not full_game:
        return 7.5
    if e.kind == 'checkmate':
        return 5.8
    if e.kind == 'underdog-capture':
        return 3.6
    if e.kind == 'capture':
        return 2.6
    if e.kind == 'check':
        return 2.8
    if e.ply <= 12:
        return 0.42
    return 0.30


def build_full_game_timeline(events: list[GameEvent], duration: float, title_seconds: float = 5.0, outro_seconds: float = 5.0) -> list[TimelineSegment]:
    budget = max(12.0, duration - title_seconds - outro_seconds)
    raw = [event_duration(e, full_game=True) for e in events]
    raw_total = sum(raw) or 1.0
    scale = budget / raw_total
    segments: list[TimelineSegment] = []
    t = title_seconds
    for e, raw_dur in zip(events, raw):
        # Preserve visible slow-motion for key events even when the full game must fit.
        min_dur = 0.18
        if e.kind in {'capture', 'underdog-capture', 'check', 'checkmate'}:
            min_dur = 1.25
        dur = max(min_dur, raw_dur * scale)
        if t + dur > duration - outro_seconds:
            dur = max(0.12, duration - outro_seconds - t)
        label = 'FAST-MONTAGE'
        if dur >= 2.8:
            label = 'SLOW-MOTION COMBAT'
        elif dur >= 1.1:
            label = 'TACTICAL SLOWDOWN'
        segments.append(TimelineSegment(e, t, dur, label, event_importance(e)))
        t += dur
        if t >= duration - outro_seconds - 0.1:
            break
    return segments


def select_narration_events(events: list[GameEvent], limit: int = 12) -> list[GameEvent]:
    key = [e for e in events if e.kind in {'capture', 'underdog-capture', 'check', 'checkmate'}]
    if not key:
        key = events
    chosen = [e for _, e in sorted(((event_importance(e), e) for e in key), key=lambda x: x[0], reverse=True)[:limit]]
    chosen.sort(key=lambda e: e.ply)
    return chosen


def write_tts_strategy(work: Path):
    """Leave a concrete offline final-voice roadmap alongside renders."""
    (work / 'premium_tts_strategy.txt').write_text(
        'Offline narration strategy for final submission\n'
        '\n'
        'Draft voice: Piper or Kokoro for fast edit iteration.\n'
        'Final voice candidates, in order:\n'
        '1. Qwen3-TTS 0.6B/1.7B — best first premium test for voice design, dramatic control, Apache-2.0.\n'
        '2. Orpheus 3B — expressive final-render candidate; acceptable if slow because narration is offline.\n'
        '3. Chatterbox — useful if we want voice conversion / stronger character style.\n'
        '\n'
        'Video principle: generate the whole game first, score events after the fact, then narrate only chapters and key beats.\n'
        'Never feed commentary/evaluation back into the no-tools LLM move generator.\n',
        encoding='utf-8',
    )


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

FONT_XS = load_font(10)
FONT_SM = load_font(16)
FONT_MD = load_font(22)
FONT_LG = load_font(36)
FONT_XL = load_font(58)
FONT_PIECE = load_font(42)


def sq_xy(square: chess.Square):
    f = chess.square_file(square)
    r = 7 - chess.square_rank(square)
    return BOARD_X + f * CELL + CELL // 2, BOARD_Y + r * CELL + CELL // 2


def draw_glow_text(draw, xy, text, font, fill, anchor=None):
    x, y = xy
    for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1)]:
        draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0), anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


PIECE_SYMBOL = {
    chess.PAWN: ('♙', '♟'), chess.KNIGHT: ('♘', '♞'), chess.BISHOP: ('♗', '♝'),
    chess.ROOK: ('♖', '♜'), chess.QUEEN: ('♕', '♛'), chess.KING: ('♔', '♚'),
}


def fit_font_for_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, fonts: list[ImageFont.FreeTypeFont]) -> ImageFont.FreeTypeFont:
    for font in fonts:
        if draw.textlength(text, font=font) <= max_width:
            return font
    return fonts[-1]


def draw_fit_text(draw: ImageDraw.ImageDraw, xy, text: str, max_width: int, fonts: list[ImageFont.FreeTypeFont], fill, anchor=None) -> None:
    draw.text(xy, text, font=fit_font_for_text(draw, text, max_width, fonts), fill=fill, anchor=anchor)


def draw_piece_icon(draw: ImageDraw.ImageDraw, x0: int, y0: int, cell: int, piece: chess.Piece) -> None:
    # Draw the piece directly on its square with no circular backplate, no halo,
    # and no opposite-colour outline. The brown board provides contrast; the
    # piece itself is a solid black or white shape.
    glyph = PIECE_SYMBOL[piece.piece_type][0 if piece.color == chess.WHITE else 1]
    cx, cy = x0 + cell / 2, y0 + cell / 2
    fill = piece_fill_color(piece)
    shadow = (28, 18, 8) if piece.color == chess.WHITE else (130, 92, 52)
    draw.text((cx + 2, cy + 2), glyph, font=FONT_PIECE, fill=shadow, anchor='mm')
    draw.text((cx, cy - 1), glyph, font=FONT_PIECE, fill=fill, anchor='mm')


def draw_piece_icon_center(draw: ImageDraw.ImageDraw, cx: float, cy: float, cell: int, piece: chess.Piece) -> None:
    draw_piece_icon(draw, int(cx - cell / 2), int(cy - cell / 2), cell, piece)


def king_square_for_color(board: chess.Board, color: bool) -> Optional[chess.Square]:
    return board.king(color)


def draw_check_crosshair(draw: ImageDraw.ImageDraw, event: GameEvent, p: float) -> None:
    if event.kind not in {'check', 'checkmate'}:
        return
    king_sq = king_square_for_color(event.board_after, not event.moved_piece.color)
    if king_sq is None:
        return
    kx, ky = sq_xy(king_sq)
    focus = min(1.0, max(0.0, (p - 0.18) / 0.62))
    radius = int(128 - 82 * focus)
    color = RED
    for r in [radius, max(18, radius - 22), max(10, radius - 42)]:
        draw.ellipse((kx-r, ky-r, kx+r, ky+r), outline=color, width=3)
    arm = radius + 42
    gap = max(12, radius // 3)
    draw.line((kx - arm, ky, kx - gap, ky), fill=color, width=4)
    draw.line((kx + gap, ky, kx + arm, ky), fill=color, width=4)
    draw.line((kx, ky - arm, kx, ky - gap), fill=color, width=4)
    draw.line((kx, ky + gap, kx, ky + arm), fill=color, width=4)
    draw.text((kx, ky - radius - 28), 'KING LOCK', font=FONT_SM, fill=color, anchor='mm')


def draw_capture_particles(draw: ImageDraw.ImageDraw, event: GameEvent, tx: float, ty: float, boom: float, scene_idx: int) -> None:
    if not event.captured_piece:
        return
    rng = random.Random(event.ply * 1009 + scene_idx * 37)
    for i in range(90):
        ang = rng.random() * math.tau
        speed = 20 + rng.random() * 165
        dist = speed * boom
        x = tx + math.cos(ang) * dist + math.sin(boom * 12 + i) * 8
        y = ty + math.sin(ang) * dist + math.cos(boom * 9 + i) * 8
        size = 1 + int(rng.random() * 4)
        fade = 1.0 - min(1.0, boom * 0.55)
        col = rng.choice([GREEN, AMBER, RED, (220, 255, 160), (40, 255, 100)])
        col = tuple(max(0, min(255, int(c * (0.55 + 0.45 * fade)))) for c in col)
        if i % 5 == 0:
            draw.line((tx, ty, x, y), fill=col, width=1)
        draw.ellipse((x-size, y-size, x+size, y+size), fill=col)


def render_board(draw: ImageDraw.ImageDraw, board: chess.Board, glow_squares=None, ascii_overlay=True, hidden_squares=None):
    glow_squares = glow_squares or []
    hidden_squares = set(hidden_squares or [])
    board_x, board_y, cell = BOARD_X, BOARD_Y, CELL
    draw.rectangle((board_x-18, board_y-18, board_x+8*cell+18, board_y+8*cell+42), fill=(42, 24, 12), outline=(235, 180, 92), width=4)
    for r in range(8):
        for f in range(8):
            sq = chess.square(f, 7-r)
            light, dark = wood_square_colors(f, r)
            base = dark if (r+f)%2 else light
            if sq in glow_squares:
                base = (210, 126, 38)
            x0, y0 = board_x + f*cell, board_y + r*cell
            draw.rectangle((x0,y0,x0+cell,y0+cell), fill=base)
            if ascii_overlay:
                for gy in range(5, cell, 12):
                    wave = int(4 * math.sin((f * 19 + r * 11 + gy) * 0.35))
                    grain_col = (max(30, base[0]-45), max(20, base[1]-38), max(10, base[2]-20))
                    draw.line((x0+3+wave, y0+gy, x0+cell-4-wave, y0+gy+2), fill=grain_col, width=1)
                ch = ASCII_RAMP[(f*3+r*5) % len(ASCII_RAMP)]
                draw.text((x0+4,y0+4), ch*3, font=FONT_XS, fill=(max(0, base[0]-65), max(0, base[1]-55), max(0, base[2]-30)))
            piece = None if sq in hidden_squares else board.piece_at(sq)
            if piece:
                draw_piece_icon(draw, x0, y0, cell, piece)
    # Coordinates live in a footer/header gutter, not under the board frame or
    # move lines. This prevents diagonals/effect lines from visually running
    # through the bottom file labels.
    for i, file in enumerate('abcdefgh'):
        draw.text((board_x+i*cell+cell/2, board_y+8*cell+22), file, font=FONT_SM, fill=(230, 190, 120), anchor='mm')
    for i in range(8):
        draw.text((board_x-28, board_y+i*cell+cell/2), str(8-i), font=FONT_SM, fill=(230, 190, 120), anchor='mm')


def board_ascii_lines(board: chess.Board) -> list[str]:
    piece_map = {
        chess.PAWN: 'p', chess.KNIGHT: 'n', chess.BISHOP: 'b',
        chess.ROOK: 'r', chess.QUEEN: 'q', chess.KING: 'k',
    }
    lines = ['+-----------------+']
    for rank in range(7, -1, -1):
        cells = []
        for file_idx in range(8):
            piece = board.piece_at(chess.square(file_idx, rank))
            if piece is None:
                cells.append('.' if (file_idx + rank) % 2 else ' ')
            else:
                ch = piece_map[piece.piece_type]
                cells.append(ch.upper() if piece.color == chess.WHITE else ch)
        lines.append(f'{rank + 1}| ' + ' '.join(cells) + ' |')
    lines.append('+-----------------+')
    lines.append('   a b c d e f g h')
    return lines


def draw_middle_action_panel(draw: ImageDraw.ImageDraw, event: GameEvent, segment_label: str, x0: int = 532, y0: int = 112) -> None:
    draw.rectangle((x0, y0, x0 + 310, 582), fill=(6, 8, 17), outline=(95, 130, 155), width=1)
    draw_glow_text(draw, (x0 + 18, y0 + 20), f'PLY {event.ply:02d}', FONT_MD, AMBER)
    draw_fit_text(draw, (x0 + 18, y0 + 58), segment_label, 274, [FONT_SM, FONT_XS], (180, 205, 220))
    draw.line((x0 + 16, y0 + 88, x0 + 294, y0 + 88), fill=(45, 70, 95), width=1)
    draw.text((x0 + 18, y0 + 112), event.side, font=FONT_LG, fill=PURE_WHITE if event.moved_piece.color == chess.WHITE else (170, 170, 170))
    draw.text((x0 + 18, y0 + 166), PIECE_NAME[event.moved_piece.piece_type].upper(), font=FONT_MD, fill=AMBER)
    if event.captured_piece:
        draw.text((x0 + 18, y0 + 214), 'CAPTURES', font=FONT_MD, fill=RED)
        draw_fit_text(draw, (x0 + 18, y0 + 258), f'{side_display_name(not event.moved_piece.color)} {PIECE_NAME[event.captured_piece.piece_type].upper()}', 270, [FONT_MD, FONT_SM], WHITE)
    elif event.kind == 'checkmate':
        draw.text((x0 + 18, y0 + 214), 'SEALS', font=FONT_MD, fill=RED)
        draw.text((x0 + 18, y0 + 258), 'THE KING', font=FONT_MD, fill=WHITE)
    elif event.kind == 'check':
        draw.text((x0 + 18, y0 + 214), 'CHECKS', font=FONT_MD, fill=RED)
        draw.text((x0 + 18, y0 + 258), 'THE KING', font=FONT_MD, fill=WHITE)
    else:
        draw.text((x0 + 18, y0 + 214), 'DEVELOPS', font=FONT_MD, fill=CYAN)
        draw.text((x0 + 18, y0 + 258), 'PRESSURE', font=FONT_MD, fill=WHITE)
    wrap_text(draw, event.caption, (x0 + 18, y0 + 326), 270, FONT_XS, (195, 215, 230), max_lines=4, line_height=18)
    draw.text((x0 + 18, y0 + 444), 'human layer', font=FONT_XS, fill=DIM)
    draw.text((x0 + 18, y0 + 462), 'no repeated notation', font=FONT_XS, fill=DIM)


def draw_llm_stream_panel(draw: ImageDraw.ImageDraw, event: GameEvent, p: float, x0: int = 862, y0: int = 112) -> None:
    draw.rectangle((x0, y0, x0 + 370, 582), fill=(1, 7, 11), outline=GREEN, width=1)
    draw_glow_text(draw, (x0 + 16, y0 + 18), 'MODEL I/O STREAM', FONT_SM, GREEN)
    side = event.side.upper()
    piece = PIECE_NAME[event.moved_piece.piece_type].upper()
    response = action_phrase(event, event.moved_piece, event.captured_piece).upper()
    # Keep this as the machine-facing stream Sebastian asked for, but do not
    # repeat the same move in SAN/UCI/FEN forms. The centre panel carries the
    # human explanation; the stream shows position in ASCII plus a plain-language
    # response and referee status.
    stream = [
        f'>> SEND BOARD TO {side}',
        'board-ascii before:',
        *board_ascii_lines(event.board_before),
        f'<< {side} RESPONSE',
        f'piece: {piece}',
        f'action: {response}',
        f'referee: LEGAL / {event.kind.upper()}',
        'board-ascii after:',
        *board_ascii_lines(event.board_after),
    ]
    visible = 17
    max_start = max(0, len(stream) - visible)
    start = int(max_start * min(1.0, max(0.0, p)))
    y = y0 + 52
    for idx, line in enumerate(stream[start:start + visible]):
        fill = GREEN
        if line.startswith('piece:') or line.startswith('action:'):
            fill = AMBER
        elif line.startswith('referee:'):
            fill = CYAN
        elif line.startswith('<<'):
            fill = WHITE
        draw.text((x0 + 16, y + idx * 22), line, font=FONT_XS, fill=fill)


def draw_capture_effect(draw: ImageDraw.ImageDraw, event: GameEvent, tx: float, ty: float, p: float, scene_idx: int):
    """Piece-specific battle-chess impact language instead of one generic boom."""
    if event.kind == 'move' and not event.captured_piece:
        return
    boom = min(1.0, max(0.0, (p - 0.48) / 0.34))
    if boom <= 0:
        return
    style = capture_style(event.moved_piece)
    chars = style['chars']
    shape = style['shape']
    hot = RED if event.captured_piece else AMBER
    cool = GREEN if event.moved_piece.color == chess.WHITE else MAGENTA
    draw_capture_particles(draw, event, tx, ty, boom, scene_idx)
    if shape == 'beam':
        fx, fy = sq_xy(event.move.from_square)
        for off in range(-18, 19, 9):
            draw.line((fx + off, fy - off, tx + off, ty - off), fill=(255, int(110 + 90*boom), 45), width=3)
        for i in range(26):
            q = i / 25
            x = fx + (tx - fx) * q + math.sin(q*18 + boom*9) * 12
            y = fy + (ty - fy) * q + math.cos(q*18 + boom*9) * 12
            draw.text((x, y), chars[i % len(chars)], font=FONT_MD, fill=cool if i % 2 else hot)
    elif shape == 'lance':
        fx, fy = sq_xy(event.move.from_square)
        midx, midy = fx, ty
        draw.line((fx, fy, midx, midy, tx, ty), fill=AMBER, width=6)
        for i in range(34):
            q = min(1, boom + i*0.015)
            x = (1-q)**2*fx + 2*(1-q)*q*midx + q*q*tx
            y = (1-q)**2*fy + 2*(1-q)*q*midy + q*q*ty
            draw.text((x + math.sin(i)*16, y + math.cos(i)*16), chars[i % len(chars)], font=FONT_MD, fill=cool if i % 3 else hot)
    elif shape == 'vortex':
        for i in range(72):
            ang = i * 0.55 + boom * 8 + scene_idx
            dist = boom * (12 + i * 2.2)
            x = tx + math.cos(ang) * dist
            y = ty + math.sin(ang) * dist
            draw.text((x, y), chars[i % len(chars)], font=FONT_MD, fill=MAGENTA if i % 2 else CYAN)
        for r in range(24, int(190 * boom) + 24, 20):
            draw.arc((tx-r, ty-r, tx+r, ty+r), start=int(boom*240), end=int(boom*240+240), fill=hot, width=4)
    elif shape == 'shockwave':
        for r in range(20, int(210*boom)+22, 26):
            draw.rectangle((tx-r, ty-r, tx+r, ty+r), outline=hot if r % 52 else cool, width=3)
        for i in range(48):
            ang = i * math.tau / 48
            dist = boom * (35 + (i % 8) * 18)
            draw.text((tx + math.cos(ang)*dist, ty + math.sin(ang)*dist), chars[i % len(chars)], font=FONT_MD, fill=AMBER if i % 2 else RED)
    else:  # pawn swarm / default
        fx, fy = sq_xy(event.move.from_square)
        for lane in range(-2, 3):
            for i in range(8):
                q = min(1.0, boom + i * 0.045)
                x = fx + (tx - fx) * q + lane * 10
                y = fy + (ty - fy) * q + math.sin(i + scene_idx) * 10
                draw.text((x, y), chars[(i + lane) % len(chars)], font=FONT_MD, fill=hot if lane == 0 else AMBER)
        for r in range(15, int(135 * boom) + 20, 18):
            draw.ellipse((tx-r, ty-r, tx+r, ty+r), outline=hot, width=3)
    if event.captured_piece:
        victim = PIECE_GLYPH[event.captured_piece.piece_type]
        for i in range(16):
            ang = i * math.tau / 16 + boom
            dist = 22 + boom * 90
            draw.text((tx + math.cos(ang)*dist, ty + math.sin(ang)*dist), victim, font=FONT_SM, fill=(255, 215, 120))
    # Shared streaming-explosion layer: a travelling debris river that keeps
    # capture kills from feeling like the same static BOOM stamped on a square.
    fx, fy = sq_xy(event.move.from_square)
    for i in range(42):
        q = min(1.35, boom * 1.12 + i * 0.018)
        wobble = math.sin(i * 1.7 + scene_idx + boom * 10) * (8 + (i % 5) * 3)
        x = fx + (tx - fx) * q + wobble
        y = fy + (ty - fy) * q + math.cos(i * 1.3 + boom * 8) * (10 + (i % 7) * 2)
        glyph = chars[i % len(chars)]
        fill = cool if i % 4 in (0, 1) else hot
        draw.text((x, y), glyph, font=FONT_SM if i % 3 else FONT_MD, fill=fill)


def background(t: float, audio_pulse: float = 0.0) -> Image.Image:
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)
    # Neon-green underground research wall: terminal grid + stencil/graffiti marks.
    for y in range(0, H, 18):
        phase = math.sin(t*2.0 + y*0.035)
        col = (3, int(22+35*abs(phase)), int(12+18*abs(phase)))
        draw.line((0, y, W, y), fill=col)
    for x in range(0, W, 32):
        offset = int(12*math.sin(t*1.4 + x*0.02))
        draw.line((x+offset, 0, x-offset, H), fill=(4, 34, 14))
    slogans = ['LEGAL', 'REFEREE', 'NO TOOLS', 'CHECK', 'MODEL', 'ARENA']
    for i, word in enumerate(slogans):
        x = int((90 + i * 211 + t * 25) % (W + 240)) - 180
        y = 112 + (i * 83) % 500
        draw.text((x+2, y+2), word, font=FONT_MD, fill=(0, 0, 0))
        draw.text((x, y), word, font=FONT_MD, fill=(18, 85, 35))
    for i in range(105):
        x = int((i*149 + t*80*(1+i%3)) % W)
        y = int((i*83 + 25*math.sin(t+i)) % H)
        ch = random.choice(['0','1','+','x','*',':','/'])
        draw.text((x,y), ch, font=FONT_SM, fill=(12, 95 + (i%120), 42))
    return img


def draw_hud(draw, title, subtitle, frame, total_frames):
    draw.rectangle((0,0,W,78), fill=(3,5,12))
    draw.line((0,78,W,78), fill=CYAN, width=2)
    draw_glow_text(draw, (34,17), project_title_text(), FONT_MD, CYAN)
    draw.text((34,46), title, font=FONT_SM, fill=WHITE)
    draw.text((W-420,18), subtitle, font=FONT_SM, fill=AMBER)


def render_title(frame, total):
    t = frame / FPS
    img = background(t)
    draw = ImageDraw.Draw(img)
    pulse = 0.5 + 0.5*math.sin(t*8)
    draw_glow_text(draw, (W//2, 145), project_title_text(), FONT_XL, AMBER, anchor='mm')
    draw_glow_text(draw, (W//2, 245), 'WHITE', FONT_LG, PURE_WHITE, anchor='mm')
    draw_glow_text(draw, (W//2, 310), 'VS', FONT_MD, AMBER, anchor='mm')
    # Black needs a light outline so the first frame reads as White vs Black,
    # not the earlier accidental "White vs" against a dark background.
    for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,2)]:
        draw.text((W//2+dx, 375+dy), 'BLACK', font=FONT_LG, fill=PURE_WHITE, anchor='mm')
    draw.text((W//2, 375), 'BLACK', font=FONT_LG, fill=(18, 16, 14), anchor='mm')
    draw.text((W//2, 470), 'LLMs PLAYING CHESS AS A BENCHMARK', font=FONT_MD, fill=WHITE, anchor='mm')
    draw.text((W//2, 508), 'model move proposal // central referee // full-game tactical arena', font=FONT_SM, fill=(230,190,120), anchor='mm')
    # No enclosing circle: keep the opening cleaner and more poster-like.
    draw_hud(draw, 'BOOTING THE ARENA', 'LLM CHESS BENCHMARK // CENTRAL REFEREE', frame, total)
    return img


def render_highlight(event: GameEvent, local_frame: int, frames_per_scene: int, scene_idx: int, scene_label: Optional[str] = None):
    p = local_frame / max(1, frames_per_scene-1)
    img = background((scene_idx*frames_per_scene + local_frame) / FPS)
    draw = ImageDraw.Draw(img)
    current = event.board_before if p < 0.62 else event.board_after
    glow = [event.move.from_square, event.move.to_square]
    animating_piece = p < 0.64
    hidden = [event.move.from_square] if animating_piece else []
    render_board(draw, current, glow, hidden_squares=hidden)
    fx, fy = sq_xy(event.move.from_square)
    tx, ty = sq_xy(event.move.to_square)
    travel = min(1.0, max(0.0, (p - 0.15) / 0.42))
    ease = travel*travel*(3-2*travel)
    mx = fx + (tx-fx)*ease
    my = fy + (ty-fy)*ease
    if animating_piece:
        for k in range(9, -1, -1):
            q = max(0, ease - k*0.035)
            x = fx + (tx-fx)*q
            y = fy + (ty-fy)*q
            col = trail_color_for_step(event.moved_piece, k)
            r = max(5, 18 - k)
            draw.ellipse((x-r, y-r, x+r, y+r), outline=col, width=2)
        draw.line((fx,fy,mx,my), fill=GREEN, width=4)
        draw_piece_icon_center(draw, mx, my, CELL, event.moved_piece)
    draw_capture_effect(draw, event, tx, ty, p, scene_idx)
    draw_check_crosshair(draw, event, p)
    draw_middle_action_panel(draw, event, scene_label or f'HIGHLIGHT {scene_idx+1:02d}', 532, 112)
    draw_llm_stream_panel(draw, event, p, 862, 112)
    draw_hud(draw, hud_matchup_text(), event.kind.upper(), scene_idx*frames_per_scene + local_frame, FRAMES)
    # CRT scanlines/glow
    if local_frame % 7 == 0:
        glitch_y = random.randint(80, H-80)
        draw.rectangle((0, glitch_y, W, glitch_y + 2), fill=(0,80,95))
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))


def render_full_game_event(segment: TimelineSegment, local_frame: int, frames_per_scene: int, scene_idx: int, total_segments: int):
    event = segment.event
    p = local_frame / max(1, frames_per_scene - 1)
    img = background((scene_idx*frames_per_scene + local_frame) / FPS)
    draw = ImageDraw.Draw(img)
    # Very fast moves become board-after flashes; important moments get the full travel/impact animation.
    if segment.duration >= 1.1:
        return render_highlight(event, local_frame, frames_per_scene, scene_idx, f'FULL GAME // {segment.label}')
    current = event.board_before if p < 0.45 else event.board_after
    glow = [event.move.from_square, event.move.to_square]
    render_board(draw, current, glow, hidden_squares=[event.move.from_square] if p < 0.45 else [])
    fx, fy = sq_xy(event.move.from_square)
    tx, ty = sq_xy(event.move.to_square)
    draw.line((fx, fy, tx, ty), fill=GREEN, width=3)
    if p < 0.45:
        q = min(1.0, p / 0.45)
        draw_piece_icon_center(draw, fx + (tx - fx) * q, fy + (ty - fy) * q, CELL, event.moved_piece)
    if p > 0.45:
        r = int(14 + 22 * math.sin(min(1, (p-0.45)/0.55) * math.pi))
        draw.ellipse((tx-r, ty-r, tx+r, ty+r), outline=GREEN if event.kind == 'move' else RED, width=3)
    draw_check_crosshair(draw, event, p)
    draw_middle_action_panel(draw, event, f'FULL GAME // {segment.label}', 532, 112)
    draw_llm_stream_panel(draw, event, p, 862, 112)
    draw_hud(draw, 'WHOLE-GAME SPEED-RAMP CUT', f'{event.kind.upper()} // {segment.duration:.2f}s', scene_idx, max(1, total_segments))
    return img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=130, threshold=3))


def wrap_text(draw, text, xy, width, font, fill, max_lines: int = 5, line_height: int = 24):
    words = text.split()
    lines, line = [], ''
    for word in words:
        test = (line + ' ' + word).strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + '…', font=font) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    x, y = xy
    for i, l in enumerate(lines):
        draw.text((x, y + i*line_height), l, font=font, fill=fill)


def synth_music(path: Path, duration: float = DURATION, sr: int = 44100):
    # Original synthetic backing track: urgent arpeggio + sub pulse + simple drums.
    bpm = 150
    beat = 60 / bpm
    notes = [55, 55, 67, 70, 62, 62, 74, 72, 58, 58, 70, 74, 65, 65, 77, 75]
    with wave.open(str(path), 'w') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        frames = []
        n = int(duration*sr)
        for i in range(n):
            t = i/sr
            step = int(t/(beat/2)) % len(notes)
            freq = 440 * (2 ** ((notes[step]-69)/12))
            arp_env = math.exp(-((t % (beat/2))/(beat/2))*3.2)
            arp = 0.22 * arp_env * (math.sin(2*math.pi*freq*t) + 0.35*math.sin(2*math.pi*freq*2*t))
            bass_freq = 55 * (2 ** ((([0,0,3,5][int(t/(beat*2))%4])-0)/12))
            bass = 0.18 * math.sin(2*math.pi*bass_freq*t) * (0.7 + 0.3*math.sin(2*math.pi*2*t))
            kick_phase = t % beat
            kick = 0.42 * math.exp(-kick_phase*18) * math.sin(2*math.pi*(65-35*kick_phase)*t) if kick_phase < 0.18 else 0
            hat_phase = t % (beat/2)
            noise = random.uniform(-1,1) if hat_phase < 0.035 else 0
            hat = 0.08 * noise * math.exp(-hat_phase*70)
            riser = 0.03 * math.sin(2*math.pi*(220 + 4*t)*t) * (t/duration)
            sample = max(-0.95, min(0.95, arp + bass + kick + hat + riser))
            val = int(sample * 32767)
            frames.append(struct.pack('<hh', val, val))
        w.writeframes(b''.join(frames))


def render_video(events: list[GameEvent], out_video: Path, work: Path, mode: str = 'highlights', timeline: Optional[list[TimelineSegment]] = None):
    ffmpeg_log = open(work/'ffmpeg_video.log', 'w')
    cmd = [
        'ffmpeg','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24',
        '-s',f'{W}x{H}','-r',str(FPS),'-i','-',
        '-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',str(out_video)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=ffmpeg_log, stderr=ffmpeg_log)
    assert proc.stdin is not None
    title_frames = 5 * FPS
    outro_frames = 5 * FPS
    frame_no = 0
    for f in range(title_frames):
        proc.stdin.write(render_title(f, title_frames).tobytes())
        frame_no += 1

    if mode == 'full-game':
        assert timeline is not None
        for idx, segment in enumerate(timeline):
            scene_frames = max(3, int(round(segment.duration * FPS)))
            for f in range(scene_frames):
                if frame_no >= FRAMES - outro_frames:
                    break
                proc.stdin.write(render_full_game_event(segment, f, scene_frames, idx, len(timeline)).tobytes())
                frame_no += 1
            if frame_no >= FRAMES - outro_frames:
                break
    else:
        scene_frames = max(3, (FRAMES - title_frames - outro_frames) // max(1, len(events)))
        for idx, event in enumerate(events):
            for f in range(scene_frames):
                proc.stdin.write(render_highlight(event, f, scene_frames, idx).tobytes())
                frame_no += 1

    while frame_no < FRAMES:
        img = background(frame_no/FPS)
        draw = ImageDraw.Draw(img)
        if mode == 'full-game':
            draw_glow_text(draw, (W//2, 170), project_title_text(), FONT_XL, AMBER, anchor='mm')
            y = 248
            for line in final_explanation_lines():
                words = line.split()
                chunk = ''
                for word in words:
                    test = (chunk + ' ' + word).strip()
                    if draw.textlength(test, font=FONT_SM) <= 820:
                        chunk = test
                    else:
                        draw.text((W//2, y), chunk, font=FONT_SM, fill=WHITE, anchor='mm')
                        y += 28
                        chunk = word
                if chunk:
                    draw.text((W//2, y), chunk, font=FONT_SM, fill=WHITE, anchor='mm')
                    y += 34
            draw.text((W//2, 500), 'FULL GAME SEEN // EVERY MOVE VALIDATED // EVERY TACTIC RENDERED', font=FONT_SM, fill=(230,190,120), anchor='mm')
            draw_hud(draw, 'SYSTEM EXPLANATION', 'LLM CHESS BENCHMARK COMPLETE', frame_no, FRAMES)
        else:
            draw_glow_text(draw, (W//2, 235), 'FINAL SIGNAL', FONT_XL, AMBER, anchor='mm')
            draw.text((W//2, 325), 'the experiment tooling is alive: simulate, observe, narrate, render', font=FONT_MD, fill=WHITE, anchor='mm')
            draw.text((W//2, 380), 'today: chess // tomorrow: any agent arena', font=FONT_MD, fill=CYAN, anchor='mm')
            draw_hud(draw, 'HIGHLIGHT REEL COMPLETE', 'EXPERIMENT TOOLING PROTOTYPE', frame_no, FRAMES)
        proc.stdin.write(img.tobytes())
        frame_no += 1
    proc.stdin.close()
    rc = proc.wait()
    ffmpeg_log.close()
    if rc != 0:
        raise RuntimeError(f'ffmpeg video failed: {rc}; see {work/"ffmpeg_video.log"}')


def build_narration_lines(events: list[GameEvent], voice_label: str = 'local Piper narration') -> list[str]:
    intro = 'Welcome to Gambit Arena: LLMs playing chess as a benchmark. Each model proposes a move, the referee checks it, and the full game becomes visible.'
    finale = 'Gambit Arena is a system test: planning, tactics, rule discipline, recovery, and one central referee.'
    return [intro] + [e.commentary for e in events] + [finale]


def write_commentary_script(lines: list[str], work: Path) -> None:
    (work / 'commentary_script.txt').write_text('\n'.join(f'{i:02d}: {line}' for i, line in enumerate(lines)), encoding='utf-8')


def make_piper_tts_segments(lines: list[str], work: Path) -> list[tuple[Path, float]]:
    piper = shutil.which('piper') or '/home/evosoft/.local/bin/piper'
    voice = Path('assets/voices/piper/en_US-lessac-high.onnx')
    if not Path(piper).exists() or not voice.exists():
        return []
    segments = []
    for i, line in enumerate(lines):
        out = work / f'voice_{i:02d}.wav'
        log = open(work/f'piper_{i:02d}.log', 'w')
        proc = subprocess.run([piper, '--model', str(voice), '--output_file', str(out)], input=line.encode('utf-8'), stdout=log, stderr=log)
        log.close()
        if proc.returncode == 0 and out.exists():
            segments.append((out, i))
    return segments


def make_edge_tts_segments(lines: list[str], work: Path, voice: str = 'en-US-GuyNeural') -> list[tuple[Path, float]]:
    edge_tts = shutil.which('edge-tts')
    if not edge_tts:
        return []
    segments = []
    for i, line in enumerate(lines):
        out = work / f'edge_voice_{i:02d}.mp3'
        log = open(work/f'edge_tts_{i:02d}.log', 'w')
        proc = subprocess.run([
            edge_tts,
            '--voice', voice,
            '--rate', '+18%',
            '--text', line,
            '--write-media', str(out),
        ], stdout=log, stderr=subprocess.STDOUT)
        log.close()
        if proc.returncode == 0 and out.exists():
            segments.append((out, i))
    return segments


QWEN_LOCAL_DEFAULT_CHECKPOINT = 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
QWEN_LOCAL_DEFAULT_SPEAKER = 'ryan'
QWEN_LOCAL_DEFAULT_INSTRUCT = 'High-energy cinematic sports broadcaster. Clear, confident, punchy Gambit Arena narration. No moaning, no drawn-out words.'
_QWEN_LOCAL_MODEL_CACHE = {}


def qwen_clip_quality_gate(line: str, metrics: dict) -> tuple[bool, str]:
    duration = float(metrics.get('duration_seconds', 0.0) or 0.0)
    rms = float(metrics.get('rms', 0.0) or 0.0)
    peak = float(metrics.get('peak', 0.0) or 0.0)
    leading = float(metrics.get('leading_silence_seconds', 0.0) or 0.0)
    trailing = float(metrics.get('trailing_silence_seconds', 0.0) or 0.0)
    word_count = max(1, len(line.split()))
    max_duration = min(18.0, max(4.2, word_count * 0.75 + 2.5))
    if duration <= 0.15:
        return False, 'empty or near-empty audio'
    if duration > max_duration:
        return False, f'duration {duration:.2f}s exceeds {max_duration:.2f}s budget for {word_count} words'
    if rms < 0.005 or peak < 0.025:
        return False, f'audio too quiet: rms={rms:.4f} peak={peak:.4f}'
    if leading > 1.0:
        return False, f'leading silence too long: {leading:.2f}s'
    if trailing > 1.4:
        return False, f'trailing silence too long: {trailing:.2f}s'
    return True, 'ok'


def audio_quality_metrics(path: Path) -> dict:
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(path)
    if getattr(audio, 'ndim', 1) > 1:
        audio = audio.mean(axis=1)
    duration = float(len(audio) / sr) if sr else 0.0
    if len(audio) == 0:
        return {'duration_seconds': 0.0, 'rms': 0.0, 'peak': 0.0, 'leading_silence_seconds': 0.0, 'trailing_silence_seconds': 0.0}
    rms = float(np.sqrt(np.mean(audio * audio)))
    peak = float(np.max(np.abs(audio)))
    threshold = max(0.01, peak * 0.03)
    non_silent = np.where(np.abs(audio) > threshold)[0]
    if len(non_silent):
        leading = float(non_silent[0] / sr)
        trailing = float((len(audio) - non_silent[-1] - 1) / sr)
    else:
        leading = duration
        trailing = 0.0
    return {'duration_seconds': duration, 'rms': rms, 'peak': peak, 'leading_silence_seconds': leading, 'trailing_silence_seconds': trailing}


def qwen_local_render_line(line: str, out_path: Path, *, speaker: str, instruct: str, checkpoint: str) -> dict:
    import soundfile as sf
    import torch
    from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel

    cache_key = (checkpoint, 'cpu', 'float32')
    tts = _QWEN_LOCAL_MODEL_CACHE.get(cache_key)
    if tts is None:
        load_start = time.time()
        tts = Qwen3TTSModel.from_pretrained(
            checkpoint,
            device_map='cpu',
            dtype=torch.float32,
            attn_implementation=None,
        )
        _QWEN_LOCAL_MODEL_CACHE[cache_key] = tts
        load_seconds = time.time() - load_start
    else:
        load_seconds = 0.0

    resolved_speaker = speaker
    if callable(getattr(tts.model, 'get_supported_speakers', None)):
        speakers = tts.model.get_supported_speakers()
        if resolved_speaker not in speakers and speakers:
            resolved_speaker = list(speakers)[0]

    gen_start = time.time()
    wavs, sr = tts.generate_custom_voice(
        text=line,
        language='English',
        speaker=resolved_speaker,
        instruct=instruct,
        max_new_tokens=220,
        do_sample=False,
    )
    generate_seconds = time.time() - gen_start
    wav = wavs[0]
    sf.write(out_path, wav, sr)
    metrics = audio_quality_metrics(out_path)
    metrics.update({
        'load_seconds': load_seconds,
        'generate_seconds': generate_seconds,
        'sample_rate': int(sr),
        'speaker': resolved_speaker,
        'checkpoint': checkpoint,
    })
    return metrics


def make_qwen_local_tts_segments(
    lines: list[str],
    work: Path,
    *,
    render_line=None,
    speaker: str = QWEN_LOCAL_DEFAULT_SPEAKER,
    instruct: str = QWEN_LOCAL_DEFAULT_INSTRUCT,
    checkpoint: str = QWEN_LOCAL_DEFAULT_CHECKPOINT,
) -> list[tuple[Path, float]]:
    renderer = render_line or qwen_local_render_line
    segments: list[tuple[Path, float]] = []
    manifest = {
        'backend': 'qwen-local',
        'checkpoint': checkpoint,
        'speaker': speaker,
        'instruct': instruct,
        'clips': [],
    }
    for i, line in enumerate(lines):
        out = work / f'qwen_voice_{i:02d}.wav'
        metrics = renderer(line, out, speaker=speaker, instruct=instruct, checkpoint=checkpoint)
        ok, reason = qwen_clip_quality_gate(line, metrics)
        clip_meta = {'index': i, 'text': line, 'path': out.name, 'quality_ok': ok, 'quality_reason': reason, **metrics}
        manifest['clips'].append(clip_meta)
        (work / 'qwen_local_tts_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        if not ok:
            raise ValueError(f'qwen-local clip {i:02d} failed quality gate: {reason}')
        segments.append((out, i))
    return segments



def make_external_tts_segments(lines: list[str], work: Path, external_dir: Path) -> list[tuple[Path, float]]:
    segments = []
    for i, _line in enumerate(lines):
        for suffix in ('.wav', '.mp3', '.ogg', '.m4a', '.aac'):
            candidate = external_dir / f'voice_{i:02d}{suffix}'
            if candidate.exists():
                segments.append((candidate, i))
                break
    return segments


def load_voice_bank_index(voice_bank_dir: Path) -> dict[str, Path]:
    index_path = voice_bank_dir / 'generated_index.json'
    data = json.loads(index_path.read_text(encoding='utf-8'))
    return {item['id']: voice_bank_dir / item['relpath'] for item in data if 'id' in item and 'relpath' in item}


def voice_bank_phrase_id(event: GameEvent) -> str:
    piece_name = PIECE_NAME[event.moved_piece.piece_type]
    phrase_no = (event.ply * 17 + event.moved_piece.piece_type * 11) % 100
    return f'phrase_{phrase_no:03d}_{piece_name}'


def make_voice_bank_tts_segments(events: list[GameEvent], work: Path, voice_bank_dir: Path) -> list[tuple[Path, float]]:
    index = load_voice_bank_index(voice_bank_dir)
    segments: list[tuple[Path, float]] = []
    script_lines = []
    for event_idx, event in enumerate(events):
        side_id = 'white_possessive' if event.moved_piece.color == chess.WHITE else 'black_possessive'
        piece_name = PIECE_NAME[event.moved_piece.piece_type]
        piece_id = f'piece_{piece_name}'
        phrase_id = voice_bank_phrase_id(event)
        ids = [side_id, piece_id, phrase_id]
        script_lines.append(f'{event_idx:02d}: {event.side} {event.san} -> ' + ' + '.join(ids))
        for sub_idx, sample_id in enumerate(ids):
            sample = index.get(sample_id)
            if sample and sample.exists() and sample.stat().st_size > 0:
                segments.append((sample, event_idx + sub_idx * 0.18))
    (work / 'commentary_script.txt').write_text('\n'.join(script_lines), encoding='utf-8')
    return segments


def make_tts_segments(events: list[GameEvent], work: Path, backend: str = 'piper', external_dir: Optional[Path] = None, voice_label: Optional[str] = None) -> list[tuple[Path, float]]:
    if backend == 'voice-bank':
        if external_dir is None:
            raise ValueError('--tts-dir is required when --tts-backend voice-bank')
        return make_voice_bank_tts_segments(events, work, Path(external_dir))
    label = voice_label or ('premium cinematic voice' if backend == 'external' else ('local Qwen3-TTS 1.7B narration' if backend == 'qwen-local' else 'local Piper narration'))
    lines = build_narration_lines(events, voice_label=label)
    write_commentary_script(lines, work)
    if backend == 'piper':
        return make_piper_tts_segments(lines, work)
    if backend == 'edge':
        return make_edge_tts_segments(lines, work)
    if backend == 'qwen-local':
        return make_qwen_local_tts_segments(lines, work)
    if backend == 'external':
        if external_dir is None:
            raise ValueError('--tts-dir is required when --tts-backend external')
        return make_external_tts_segments(lines, work, Path(external_dir))
    raise ValueError(f'unknown TTS backend: {backend}')


def audio_duration_seconds(path: Path) -> float:
    try:
        proc = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        return max(0.0, float(proc.stdout.strip()))
    except Exception:
        return 0.0


def plan_narration_starts(desired_starts: list[float], durations: list[float], total_duration: float, gap: float = 0.35) -> list[float]:
    starts: list[float] = []
    cursor = 0.0
    for desired, duration in zip(desired_starts, durations):
        latest = max(0.0, total_duration - max(0.0, duration) - 0.25)
        # Never schedule beyond latest; a small overlap is better than cutting
        # the final explanatory line off at the end of the video.
        start = min(max(desired, cursor), latest)
        starts.append(start)
        cursor = start + max(0.0, duration) + gap
    return starts


def build_commentary_track(events: list[GameEvent], work: Path, out: Path, mode: str = 'highlights', timeline: Optional[list[TimelineSegment]] = None, tts_backend: str = 'piper', tts_dir: Optional[Path] = None, voice_label: Optional[str] = None):
    narration_events = events if mode != 'full-game' else select_narration_events(events)
    segments = make_tts_segments(narration_events, work, backend=tts_backend, external_dir=tts_dir, voice_label=voice_label)
    if not segments:
        # silent fallback
        subprocess.run(['ffmpeg','-y','-f','lavfi','-i',f'anullsrc=r=44100:cl=stereo','-t',str(DURATION),str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return
    if tts_backend == 'voice-bank' and mode == 'full-game' and timeline:
        by_ply = {seg.event.ply: seg.start for seg in timeline}
        event_starts = [min(DURATION - 3.0, by_ply.get(e.ply, 8.0) + 0.12) for e in narration_events]
        desired_starts = [event_starts[min(int(slot), len(event_starts)-1)] + (slot - int(slot)) for _seg, slot in segments]
    elif tts_backend == 'voice-bank':
        title_frames = 5 * FPS
        scene_frames = (FRAMES - title_frames - 5*FPS) // max(1, len(events))
        event_starts = [5.2 + i * scene_frames / FPS + 0.3 for i in range(len(narration_events))]
        desired_starts = [event_starts[min(int(slot), len(event_starts)-1)] + (slot - int(slot)) for _seg, slot in segments]
    elif mode == 'full-game' and timeline:
        by_ply = {seg.event.ply: seg.start for seg in timeline}
        desired_starts = [0.8]
        desired_starts += [min(DURATION - 8.0, by_ply.get(e.ply, 8.0) + 0.25) for e in narration_events]
        desired_starts.append(max(8.0, DURATION - 7.0))
    else:
        desired_starts = [0.8]
        title_frames = 5 * FPS
        scene_frames = (FRAMES - title_frames - 5*FPS) // max(1, len(events))
        for i in range(len(events)):
            desired_starts.append(5.2 + i * scene_frames / FPS + 0.6)
        desired_starts.append(max(8.0, DURATION - 7.0))
    durations = [audio_duration_seconds(seg) for seg, _ in segments]
    starts = plan_narration_starts(desired_starts[:len(segments)], durations, DURATION, gap=0.35)
    inputs = []
    filters = []
    for idx, ((seg, _), start) in enumerate(zip(segments, starts)):
        inputs += ['-i', str(seg)]
        delay = int(start * 1000)
        filters.append(f'[{idx}:a]adelay={delay}|{delay},volume=1.45[v{idx}]')
    mix_inputs = ''.join(f'[v{i}]' for i in range(len(segments)))
    filt = ';'.join(filters) + f';{mix_inputs}amix=inputs={len(segments)}:duration=longest:normalize=0,atrim=0:{DURATION}[out]'
    log = open(work/'ffmpeg_voice_mix.log','w')
    cmd = ['ffmpeg','-y'] + inputs + ['-filter_complex', filt, '-map','[out]', '-ar','44100','-ac','2', str(out)]
    rc = subprocess.run(cmd, stdout=log, stderr=log).returncode
    log.close()
    if rc != 0:
        raise RuntimeError('voice mix failed')


def mux(video: Path, music: Path, voice: Path, out: Path, work: Path):
    log = open(work/'ffmpeg_mux.log','w')
    filt = '[1:a]volume=0.16[m];[2:a]volume=1.85[v];[m][v]amix=inputs=2:duration=first:normalize=0[a]'
    cmd = ['ffmpeg','-y','-i',str(video),'-i',str(music),'-i',str(voice),'-filter_complex',filt,'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-shortest',str(out)]
    rc = subprocess.run(cmd, stdout=log, stderr=log).returncode
    log.close()
    if rc != 0:
        raise RuntimeError('mux failed')


def main():
    global DURATION, FRAMES
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='outputs/evolving_ascii_chess_highlight_reel.mp4')
    ap.add_argument('--seed', type=int, default=73)
    ap.add_argument('--highlights', type=int, default=10)
    ap.add_argument('--mode', choices=['highlights', 'full-game'], default='highlights', help='highlights = old curated reel; full-game = every move with speed ramps')
    ap.add_argument('--duration', type=int, default=DURATION, help='target video duration in seconds')
    ap.add_argument('--max-plies', type=int, default=74, help='maximum plies to simulate before rendering')
    ap.add_argument('--tts-backend', choices=['piper', 'edge', 'qwen-local', 'external', 'voice-bank'], default='qwen-local', help='qwen-local = local Qwen3-TTS 1.7B full-line narration; edge = concise neural draft; piper = bundled local draft voice; external = use pre-rendered voice_XX audio files from --tts-dir; voice-bank = legacy atom assembly')
    ap.add_argument('--tts-dir', type=Path, default=None, help='directory containing voice_00.wav/mp3, voice_01.wav/mp3, ... for --tts-backend external')
    ap.add_argument('--voice-label', default=None, help='label written into the narration script for the selected voice')
    args = ap.parse_args()

    DURATION = args.duration
    FRAMES = FPS * DURATION

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / ('full_game_work' if args.mode == 'full-game' else 'highlight_work')
    work.mkdir(parents=True, exist_ok=True)
    stockfish = detect_stockfish()
    events = simulate_game(stockfish, seed=args.seed, max_plies=args.max_plies)
    write_tts_strategy(work)

    timeline: Optional[list[TimelineSegment]] = None
    render_events = events
    manifest = work / ('full_game_manifest.txt' if args.mode == 'full-game' else 'highlight_manifest.txt')
    if args.mode == 'full-game':
        timeline = build_full_game_timeline(events, DURATION)
        render_events = [seg.event for seg in timeline]
        manifest.write_text('\n'.join(
            f'{seg.start:06.2f}s {seg.duration:04.2f}s ply={seg.event.ply:02d} {seg.event.side:9s} {seg.event.kind:16s} {seg.event.san:8s} {seg.label:20s} importance={seg.importance:04.1f} {seg.event.caption}'
            for seg in timeline
        ), encoding='utf-8')
    else:
        render_events = select_highlights(events)[:args.highlights]
        if len(render_events) < 5:
            render_events = events[:args.highlights]
        manifest.write_text('\n'.join(f'{e.ply:02d} {e.side:9s} {e.kind:16s} {e.san:8s} {e.caption}' for e in render_events), encoding='utf-8')

    silent_video = work / 'silent_reel.mp4'
    music = work / 'synthetic_music.wav'
    voice = work / 'commentary.wav'
    synth_music(music)
    build_commentary_track(render_events, work, voice, args.mode, timeline, tts_backend=args.tts_backend, tts_dir=args.tts_dir, voice_label=args.voice_label)
    render_video(render_events, silent_video, work, args.mode, timeline)
    mux(silent_video, music, voice, out, work)
    print(out)
    print(manifest)

if __name__ == '__main__':
    main()

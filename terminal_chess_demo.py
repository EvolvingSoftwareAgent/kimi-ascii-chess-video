#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chess
import chess.engine
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()
FILES = 'abcdefgh'
RANKS = '12345678'
PIECES = {
    'P': 'P', 'N': 'N', 'B': 'B', 'R': 'R', 'Q': 'Q', 'K': 'K',
    'p': 'p', 'n': 'n', 'b': 'b', 'r': 'r', 'q': 'q', 'k': 'k',
}
LIGHT_STYLE = 'black on bright_white'
DARK_STYLE = 'white on grey23'
HILITE_FROM = 'black on bright_cyan'
HILITE_TO = 'black on bright_green'
IMPACT_STYLE = 'bold bright_yellow on red'
TRAIL_STYLE = 'bold bright_magenta'
INFO_STYLE = 'bright_white'
ALARM_STYLE = 'bold bright_white on red'
TITLE_STYLE = 'bold bright_cyan'
SAN_TOKEN_RE = re.compile(r'(?<![A-Za-z0-9])(?:O-O-O|O-O|0-0-0|0-0|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)(?![A-Za-z0-9])')
UCI_RE = re.compile(r'\b([a-h][1-8][a-h][1-8][qrbnQRBN]?)\b')
SQUARE_RE = re.compile(r'\b([a-h][1-8])\b')


@dataclass
class MoveDecision:
    move: chess.Move
    san: str
    raw: str
    source: str
    candidate: str = ''
    attempts: int = 1
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class MatchEvent:
    kind: str
    ply: int
    side: str
    message: str
    san: str = ''
    uci: str = ''
    source: str = ''


class PlayerAdapter:
    name: str
    is_ai: bool = False

    def choose_move(self, board: chess.Board, move_history: list[str]) -> MoveDecision:
        raise NotImplementedError

    def close(self) -> None:
        return None


class RandomLegalPlayer(PlayerAdapter):
    def __init__(self, name: str = 'MockLLM', is_ai: bool = True) -> None:
        self.name = name
        self.is_ai = is_ai

    def choose_move(self, board: chess.Board, move_history: list[str]) -> MoveDecision:
        legal = list(board.legal_moves)
        move = random.choice(legal)
        san = board.san(move)
        return MoveDecision(move=move, san=san, raw=san, candidate=san, source='random-legal')


class StockfishPlayer(PlayerAdapter):
    def __init__(self, engine_path: str, think_time: float, name: str = 'Stockfish') -> None:
        self.name = name
        self.engine_path = engine_path
        self.think_time = think_time
        self.is_ai = False
        self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)

    def choose_move(self, board: chess.Board, move_history: list[str]) -> MoveDecision:
        result = self.engine.play(board, chess.engine.Limit(time=self.think_time))
        move = result.move
        san = board.san(move)
        return MoveDecision(move=move, san=san, raw=san, candidate=san, source='stockfish')

    def close(self) -> None:
        self.engine.quit()


class OpenAICompatibleLLMPlayer(PlayerAdapter):
    def __init__(
        self,
        name: str = 'LLM',
        env_prefix: str = 'KIMI',
        fallback: Optional[PlayerAdapter] = None,
        temperature: float = 0.2,
        max_retries: int = 3,
        timeout: float = 25.0,
        log_path: Optional[Path] = None,
    ) -> None:
        self.name = name
        self.env_prefix = env_prefix
        self.temperature = temperature
        self.max_retries = max(0, max_retries)
        self.timeout = timeout
        self.api_key = os.getenv(f'{env_prefix}_API_KEY', '')
        self.model = os.getenv(f'{env_prefix}_MODEL', 'kimi-k2')
        self.base_url = os.getenv(f'{env_prefix}_BASE_URL', 'https://api.moonshot.ai/v1/chat/completions')
        self.fallback = fallback or RandomLegalPlayer(name=f'{name}-fallback')
        self.is_ai = True
        env_log = os.getenv(f'{env_prefix}_RAW_LOG', '')
        self.log_path = Path(env_log) if env_log else log_path

    def choose_move(self, board: chess.Board, move_history: list[str]) -> MoveDecision:
        if not self.api_key:
            fallback_decision = self.fallback.choose_move(board, move_history)
            return MoveDecision(
                move=fallback_decision.move,
                san=fallback_decision.san,
                raw=fallback_decision.raw,
                candidate=fallback_decision.candidate or fallback_decision.san,
                source='fallback:no-api-key',
                diagnostics=['KIMI_API_KEY missing; used random legal fallback'],
            )

        diagnostics: list[str] = []
        raw_outputs: list[str] = []
        legal_san = [board.san(move) for move in board.legal_moves]
        constrained_from: Optional[chess.Square] = None
        constrained_legal = legal_san

        for attempt in range(1, self.max_retries + 2):
            prompt = self._build_prompt(board, move_history, constrained_legal, attempt, constrained_from, diagnostics[-2:])
            try:
                raw = self._call_api(prompt)
            except Exception as exc:
                diagnostics.append(f'attempt {attempt}: api error {type(exc).__name__}: {exc}')
                raw_outputs.append(f'<api-error:{type(exc).__name__}:{exc}>')
                continue

            raw_outputs.append(raw)
            move, candidate, parse_note = self._extract_move(raw, board, constrained_legal)
            self._log_raw(board, attempt, raw, candidate, parse_note, constrained_from)
            if move is not None:
                san = board.san(move)
                return MoveDecision(
                    move=move,
                    san=san,
                    raw=raw,
                    candidate=candidate or san,
                    source='llm' if attempt == 1 else f'llm:retry-{attempt}',
                    attempts=attempt,
                    diagnostics=diagnostics,
                )

            diagnostics.append(f'attempt {attempt}: invalid output {candidate or raw[:60]!r} ({parse_note})')
            touched = recover_touched_square(raw, candidate, board)
            if touched is not None:
                touch_moves = [move for move in board.legal_moves if move.from_square == touched]
                if touch_moves:
                    constrained_from = touched
                    constrained_legal = [board.san(move) for move in touch_moves]
                    diagnostics.append(
                        f'AI touch rule: constrained retry to touched source square {chess.square_name(touched)}'
                    )
                else:
                    constrained_from = None
                    constrained_legal = legal_san
                    diagnostics.append(f'AI touch rule: {chess.square_name(touched)} has no legal moves; unconstrained retry')
            else:
                constrained_from = None
                constrained_legal = legal_san

        fallback_decision = self.fallback.choose_move(board, move_history)
        return MoveDecision(
            move=fallback_decision.move,
            san=fallback_decision.san,
            raw=' | '.join(raw_outputs[-3:]),
            candidate=fallback_decision.candidate or fallback_decision.san,
            source='fallback:llm-retry-budget-exhausted',
            attempts=self.max_retries + 1,
            diagnostics=diagnostics,
        )

    def _build_prompt(
        self,
        board: chess.Board,
        move_history: list[str],
        legal_san: list[str],
        attempt: int,
        constrained_from: Optional[chess.Square],
        recent_errors: list[str],
    ) -> str:
        last_moves = ', '.join(move_history[-12:]) if move_history else 'none'
        constraint = ''
        if constrained_from is not None:
            constraint = (
                f'\nTouch-move arbitration is active. You previously touched '
                f'{chess.square_name(constrained_from)}; propose a legal move using that same piece.'
            )
        errors = ('\nRecent invalid outputs: ' + ' | '.join(recent_errors)) if recent_errors else ''
        return (
            'You are playing a chess game with no tools and no board rendering. '
            'Return exactly one legal chess move in SAN if possible, or UCI if needed, and nothing else.\n\n'
            f'Attempt: {attempt}\n'
            f'FEN: {board.fen()}\n'
            f'Side to move: {"White" if board.turn == chess.WHITE else "Black"}\n'
            f'Last moves: {last_moves}'
            f'{constraint}{errors}\n\n'
            'Rules: infer the move yourself from the position. The referee will check legality after you answer. '
            'No explanation. No prose. No markdown. Just one move.'
        )

    def _call_api(self, prompt: str) -> str:
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': 'You are a no-tools chess move generator. Infer one move from the position. Output only the move; the referee checks legality after you answer.'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': self.temperature,
            'max_tokens': 24,
        }
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')[:500]
            raise RuntimeError(f'HTTP {exc.code}: {body}') from exc
        return data['choices'][0]['message']['content'].strip()

    @staticmethod
    def _extract_move(raw: str, board: chess.Board, legal_san: list[str]) -> tuple[Optional[chess.Move], str, str]:
        cleaned = raw.strip().strip('`').strip()
        candidates: list[str] = []
        if cleaned:
            candidates.append(cleaned.splitlines()[0].strip().strip('`').strip())
        candidates.extend(match.group(0) for match in SAN_TOKEN_RE.finditer(raw.replace('0-0', 'O-O')))

        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.strip().rstrip('.,;')
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            normalized = candidate.replace('0-0-0', 'O-O-O').replace('0-0', 'O-O')
            if normalized not in legal_san:
                continue
            try:
                return board.parse_san(normalized), normalized, 'san-exact'
            except Exception:
                pass

        for match in UCI_RE.finditer(raw):
            uci = match.group(1).lower()
            try:
                move = chess.Move.from_uci(uci)
            except ValueError:
                continue
            if move in board.legal_moves:
                return move, uci, 'uci-fallback'
        return None, candidates[0] if candidates else '', 'no legal SAN/UCI candidate found'

    def _log_raw(
        self,
        board: chess.Board,
        attempt: int,
        raw: str,
        candidate: str,
        parse_note: str,
        constrained_from: Optional[chess.Square],
    ) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'player': self.name,
            'model': self.model,
            'attempt': attempt,
            'fen': board.fen(),
            'candidate': candidate,
            'parse_note': parse_note,
            'constrained_from': chess.square_name(constrained_from) if constrained_from is not None else None,
            'raw': raw,
        }
        with self.log_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')


def recover_touched_square(raw: str, candidate: str, board: chess.Board) -> Optional[chess.Square]:
    text = ' '.join(part for part in (candidate, raw) if part)
    for match in UCI_RE.finditer(text):
        sq = chess.parse_square(match.group(1)[:2].lower())
        piece = board.piece_at(sq)
        if piece and piece.color == board.turn:
            return sq
    for match in SQUARE_RE.finditer(text):
        sq = chess.parse_square(match.group(1).lower())
        piece = board.piece_at(sq)
        if piece and piece.color == board.turn:
            return sq
    return None


def square_name(file_idx: int, rank_idx: int) -> str:
    return f"{FILES[file_idx]}{RANKS[7-rank_idx]}"


def board_to_lines(
    board: chess.Board,
    highlight_from: Optional[chess.Square] = None,
    highlight_to: Optional[chess.Square] = None,
    trail_progress: float = 1.0,
    moving_piece: Optional[str] = None,
    explosion_square: Optional[chess.Square] = None,
    explosion_phase: int = 0,
    alarm: bool = False,
) -> Text:
    text = Text()
    header_style = 'bold bright_red' if alarm else 'bold white'
    text.append('    a    b    c    d    e    f    g    h\n', style=header_style)
    for rank_idx in range(8):
        border_style = 'bright_red' if alarm and rank_idx % 2 == 0 else 'grey50'
        text.append('  +' + '----+' * 8 + f'\n', style=border_style)
        text.append(f'{8-rank_idx} ', style=header_style)
        for file_idx in range(8):
            sq_name = square_name(file_idx, rank_idx)
            square = chess.parse_square(sq_name)
            piece = board.piece_at(square)
            piece_char = PIECES.get(piece.symbol(), ' ') if piece else ' '
            style = LIGHT_STYLE if (file_idx + rank_idx) % 2 == 0 else DARK_STYLE
            if alarm and board.king(board.turn) == square:
                style = ALARM_STYLE
            if square == highlight_from:
                style = HILITE_FROM
            elif square == highlight_to:
                style = HILITE_TO
            cell = f' {piece_char}  '

            if highlight_from is not None and highlight_to is not None and moving_piece:
                fx, fy = chess.square_file(highlight_from), 7 - chess.square_rank(highlight_from)
                tx, ty = chess.square_file(highlight_to), 7 - chess.square_rank(highlight_to)
                px = round(fx + (tx - fx) * trail_progress)
                py = round(fy + (ty - fy) * trail_progress)
                if file_idx == px and rank_idx == py:
                    cell = f' {moving_piece}  '
                    style = TRAIL_STYLE

            if explosion_square is not None and square == explosion_square:
                sparks = [' *  ', 'xXx ', ' BO ', 'OM! ', ' ** ', ' .. ']
                cell = sparks[min(explosion_phase, len(sparks) - 1)].ljust(4)[:4]
                style = IMPACT_STYLE

            text.append('|', style=border_style)
            text.append(cell, style=style)
        text.append('|\n', style=border_style)
    text.append('  +' + '----+' * 8 + '\n', style='bright_red' if alarm else 'grey50')
    return text


class TerminalMatch:
    def __init__(
        self,
        llm_player: PlayerAdapter,
        engine_player: PlayerAdapter,
        max_plies: int = 60,
        fps: int = 8,
        intro: bool = True,
    ) -> None:
        self.board = chess.Board()
        self.llm_player = llm_player
        self.engine_player = engine_player
        self.max_plies = max_plies
        self.frame_delay = 1.0 / max(fps, 1)
        self.move_history: list[str] = []
        self.events: list[MatchEvent] = []
        self.status = 'Ready'
        self.last_raw = ''
        self.banner = ''
        self.intro = intro

    def current_player(self) -> PlayerAdapter:
        return self.llm_player if self.board.turn == chess.WHITE else self.engine_player

    def emit(self, kind: str, message: str, decision: Optional[MoveDecision] = None) -> None:
        side = 'White' if self.board.turn == chess.WHITE else 'Black'
        self.events.append(MatchEvent(
            kind=kind,
            ply=len(self.move_history),
            side=side,
            message=message,
            san=decision.san if decision else '',
            uci=decision.move.uci() if decision else '',
            source=decision.source if decision else '',
        ))
        self.banner = message

    def render(self, body: Text) -> Group:
        meta = Text()
        meta.append(f'White: {self.llm_player.name}    ', style='bold bright_white')
        meta.append(f'Black: {self.engine_player.name}\n', style='bold bright_white')
        meta.append(f'Ply: {len(self.move_history)}    ', style=INFO_STYLE)
        meta.append(f'Turn: {"White" if self.board.turn == chess.WHITE else "Black"}\n', style=INFO_STYLE)
        meta.append(f'Status: {self.status}\n', style='bold bright_yellow')
        if self.banner:
            meta.append(f'Event: {self.banner}\n', style='bold bright_red' if self.board.is_check() else 'bold bright_green')
        if self.move_history:
            meta.append('Moves: ' + ' '.join(self.move_history[-12:]) + '\n', style='bright_cyan')
        if self.events:
            recent = ' | '.join(f'{event.kind}:{event.san or event.message}' for event in self.events[-4:])
            meta.append(f'Event stream: {recent}\n', style='bright_magenta')
        if self.last_raw:
            meta.append(f'Raw chooser output: {self.last_raw[:180]}', style='bright_black')
        return Group(
            Panel(body, title='Chess Arena // RAW LANGUAGE INTELLIGENCE VS CLASSICAL SEARCH', border_style='bright_blue'),
            Panel(meta, title='Match Telemetry / Referee Bus', border_style='bright_magenta'),
        )

    def title_card(self) -> Group:
        title = Text()
        title.append('\n  CHESS ARENA\n', style=TITLE_STYLE)
        title.append('  RAW LANGUAGE INTELLIGENCE ENTERS THE ARENA\n\n', style='bold bright_white')
        title.append(f'  {self.llm_player.name}  ', style='bold bright_cyan')
        title.append('VS', style='bold bright_yellow')
        title.append(f'  {self.engine_player.name}\n\n', style='bold bright_red')
        title.append('  no tools // legal referee // terminal-native spectacle\n', style='bright_black')
        return Group(Panel(Align.center(title), title='BOOT SEQUENCE', border_style='bright_cyan'))

    def animate_intro(self, live: Live) -> None:
        if not self.intro:
            return
        for pulse in range(6):
            self.status = 'Arena booting' + '.' * (pulse % 4)
            live.update(self.title_card(), refresh=True)
            time.sleep(max(self.frame_delay * 2, 0.08))

    def animate_move(self, live: Live, move: chess.Move, piece_symbol: str) -> None:
        for phase in range(5):
            body = board_to_lines(
                self.board,
                highlight_from=move.from_square,
                highlight_to=move.to_square,
                trail_progress=phase / 4,
                moving_piece=piece_symbol,
                alarm=self.board.is_check(),
            )
            live.update(self.render(body), refresh=True)
            time.sleep(self.frame_delay)

    def animate_capture(self, live: Live, square: chess.Square) -> None:
        for phase in range(6):
            body = board_to_lines(self.board, highlight_to=square, explosion_square=square, explosion_phase=phase, alarm=self.board.is_check())
            live.update(self.render(body), refresh=True)
            time.sleep(self.frame_delay)

    def animate_check(self, live: Live) -> None:
        for phase in range(4):
            self.banner = 'CHECK WARNING' if phase % 2 == 0 else 'KING UNDER FIRE'
            body = board_to_lines(self.board, alarm=True)
            live.update(self.render(body), refresh=True)
            time.sleep(self.frame_delay)

    def end_card(self, result: str) -> Group:
        card = Text()
        card.append('\n  GAME OVER\n', style='bold bright_yellow')
        card.append(f'  Result: {result}\n', style='bold bright_white')
        card.append(f'  Plies: {len(self.move_history)}\n', style='bright_cyan')
        if self.move_history:
            card.append(f'  Final line: {" ".join(self.move_history[-16:])}\n', style='bright_magenta')
        card.append('\n  referee log intact // spectacle complete\n', style='bright_black')
        return Group(Panel(Align.center(card), title='FINAL POSITION', border_style='bright_yellow'))

    def run(self) -> str:
        with Live(self.render(board_to_lines(self.board)), console=console, refresh_per_second=20, screen=False) as live:
            self.animate_intro(live)
            live.update(self.render(board_to_lines(self.board)), refresh=True)
            while not self.board.is_game_over() and len(self.move_history) < self.max_plies:
                player = self.current_player()
                self.status = f'{player.name} thinking'
                self.banner = ''
                live.update(self.render(board_to_lines(self.board, alarm=self.board.is_check())), refresh=True)
                decision = player.choose_move(self.board, self.move_history)
                for diagnostic in decision.diagnostics:
                    self.emit('invalid-retry' if 'invalid' in diagnostic else 'adapter-note', diagnostic, decision)
                self.last_raw = f'{decision.source}: {decision.raw}'
                self.emit('move-proposed', f'{player.name} proposes {decision.san}', decision)
                if decision.move not in self.board.legal_moves:
                    raise RuntimeError(f'{player.name} returned illegal move after arbitration: {decision.move.uci()}')
                moving_piece = self.board.piece_at(decision.move.from_square)
                moving_symbol = PIECES.get(moving_piece.symbol(), '?') if moving_piece else '?'
                captured = self.board.is_capture(decision.move)
                self.status = f'{player.name} plays {decision.san}'
                self.emit('move-accepted', f'{player.name} plays {decision.san}', decision)
                self.animate_move(live, decision.move, moving_symbol)
                self.board.push(decision.move)
                self.move_history.append(decision.san)
                if captured:
                    self.status = f'Impact! {decision.san}'
                    self.emit('capture', f'IMPACT on {chess.square_name(decision.move.to_square)}', decision)
                    self.animate_capture(live, decision.move.to_square)
                if self.board.is_checkmate():
                    self.status = f'Checkmate! {decision.san}'
                    self.emit('checkmate', 'CHECKMATE // terminal arena locked', decision)
                    self.animate_check(live)
                elif self.board.is_check():
                    self.status = f'Check! {decision.san}'
                    self.emit('check', 'CHECK WARNING', decision)
                    self.animate_check(live)
                else:
                    live.update(self.render(board_to_lines(self.board, highlight_to=decision.move.to_square)), refresh=True)
                    time.sleep(self.frame_delay)
            result = self.board.result(claim_draw=True)
            self.status = f'Game over: {result}'
            live.update(self.end_card(result), refresh=True)
            time.sleep(0.5)
        return result


def detect_stockfish() -> str:
    for candidate in ('stockfish', '/usr/games/stockfish', '/usr/bin/stockfish'):
        path = shutil.which(candidate) if '/' not in candidate else candidate
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError('Stockfish binary not found')


def build_players(args: argparse.Namespace) -> tuple[PlayerAdapter, PlayerAdapter]:
    engine = StockfishPlayer(engine_path=args.engine_path, think_time=args.engine_time, name=args.engine_name)
    log_path = Path(args.llm_raw_log) if args.llm_raw_log else None
    if args.llm_mode == 'kimi':
        llm = OpenAICompatibleLLMPlayer(
            name=args.llm_name,
            temperature=args.llm_temperature,
            max_retries=args.llm_retries,
            timeout=args.llm_timeout,
            log_path=log_path,
        )
    else:
        llm = RandomLegalPlayer(name=args.llm_name)
    return llm, engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Chess Arena: LLM vs classical engine')
    parser.add_argument('--llm-mode', choices=['kimi', 'random'], default='random')
    parser.add_argument('--llm-name', default='LLM')
    parser.add_argument('--engine-name', default='Stockfish')
    parser.add_argument('--engine-path', default=detect_stockfish())
    parser.add_argument('--engine-time', type=float, default=0.05)
    parser.add_argument('--max-plies', type=int, default=40)
    parser.add_argument('--fps', type=int, default=8)
    parser.add_argument('--no-intro', action='store_true', help='Skip cinematic title card for fast smoke tests')
    parser.add_argument('--llm-retries', type=int, default=3, help='Malformed/illegal LLM output retry budget before fallback')
    parser.add_argument('--llm-timeout', type=float, default=25.0, help='HTTP timeout for each LLM call')
    parser.add_argument('--llm-temperature', type=float, default=0.2)
    parser.add_argument('--llm-raw-log', default='', help='Optional JSONL log path for raw LLM outputs')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    llm, engine = build_players(args)
    try:
        match = TerminalMatch(
            llm_player=llm,
            engine_player=engine,
            max_plies=args.max_plies,
            fps=args.fps,
            intro=not args.no_intro,
        )
        result = match.run()
        console.print(f'Final result: {result}', style='bold bright_green')
        return 0
    finally:
        llm.close()
        engine.close()


if __name__ == '__main__':
    raise SystemExit(main())

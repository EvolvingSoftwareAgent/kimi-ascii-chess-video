#!/usr/bin/env python3
"""Build a game-style reusable voice sample manifest for Gambit Arena.

The manifest separates short announcer atoms ("White's", "Black's") from reusable
piece-action lines ("knight goes in for a kill..."). That lets the renderer stitch
samples together like a game audio system rather than rendering bespoke narration
for every move.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SIDES = [
    {"id": "white_possessive", "text": "White's", "category": "side_prefix"},
    {"id": "black_possessive", "text": "Black's", "category": "side_prefix"},
]

PIECES = ["pawn", "knight", "bishop", "rook", "queen", "king"]

PHRASE_TEMPLATES = [
    "{piece} goes in for a kill and leaves itself in a precarious position.",
    "{piece} cuts through the grid and dares the reply.",
    "{piece} steps into danger, but the pressure lands first.",
    "{piece} takes the hit square and makes the board answer.",
    "{piece} moves like bait with teeth.",
    "{piece} enters the lane and the whole position tightens.",
    "{piece} finds contact and turns silence into alarm.",
    "{piece} crosses the line and the arena flares.",
    "{piece} commits forward; retreat is no longer the story.",
    "{piece} makes the capture feel personal.",
    "{piece} attacks low and changes the value of the room.",
    "{piece} lands on a square that suddenly matters.",
    "{piece} drags the fight into the open.",
    "{piece} applies pressure where the king can hear it.",
    "{piece} takes space and leaves a question behind.",
    "{piece} becomes the problem the engine has to solve.",
    "{piece} makes a quiet move with loud consequences.",
    "{piece} breaks the pattern and the board starts blinking.",
    "{piece} turns a normal square into a threat marker.",
    "{piece} does not ask permission; it enters.",
    "{piece} starts a small fire on the far side of the board.",
    "{piece} leans into the tactic before it is safe.",
    "{piece} forces the camera to follow.",
    "{piece} trades comfort for initiative.",
    "{piece} grabs material and invites trouble.",
    "{piece} makes the opponent count every escape route.",
    "{piece} opens a corridor that did not exist a move ago.",
    "{piece} plants itself where calculation gets expensive.",
    "{piece} turns the corner and finds impact.",
    "{piece} makes the position feel less stable.",
    "{piece} walks into the storm with a knife out.",
    "{piece} converts tension into contact.",
    "{piece} shifts the tempo and the map redraws itself.",
    "{piece} takes the dangerous square because danger is the point.",
    "{piece} puts a red light on the king's neighborhood.",
    "{piece} gets active and the board stops being polite.",
    "{piece} makes a move that looks small until it echoes.",
    "{piece} finds the loose thread and pulls.",
    "{piece} steps into the highlight frame.",
    "{piece} becomes the weapon and the warning.",
    "{piece} hits the square like a dropped match.",
    "{piece} changes lanes and the defense loses shape.",
    "{piece} turns pressure into a visible wound.",
    "{piece} asks a question the opponent cannot ignore.",
    "{piece} moves with just enough chaos to matter.",
    "{piece} takes the long road to a short threat.",
    "{piece} enters the engine room and starts pulling cables.",
    "{piece} makes the next capture feel inevitable.",
    "{piece} throws a shadow across the back rank.",
    "{piece} carries the attack one square deeper.",
    "{piece} finds a seam and pushes through it.",
    "{piece} adds weight to a file that was already groaning.",
    "{piece} becomes a siren pointed at the king.",
    "{piece} leaves safety behind and buys initiative.",
    "{piece} moves with the confidence of a loaded trap.",
    "{piece} turns the board into a smaller place.",
    "{piece} cuts off a route before anyone names it.",
    "{piece} puts pressure on the position's weakest nerve.",
    "{piece} finds a tactical pocket and climbs inside.",
    "{piece} makes the defense choose what to abandon.",
    "{piece} turns a developing move into a warning shot.",
    "{piece} takes a square and taxes every reply.",
    "{piece} moves first; the explanation arrives later.",
    "{piece} starts the countdown on the wrong side of the board.",
    "{piece} makes the center feel radioactive.",
    "{piece} slips past the front line and changes the weather.",
    "{piece} converts a loose square into a crime scene.",
    "{piece} makes the opponent defend with both hands.",
    "{piece} reaches the danger zone and refuses to blink.",
    "{piece} turns initiative into a physical object.",
    "{piece} advances like the tactic already happened.",
    "{piece} hits the board and the silence breaks.",
    "{piece} makes the whole position lean sideways.",
    "{piece} carries threat energy into a quiet square.",
    "{piece} goes hunting and leaves fingerprints.",
    "{piece} makes a capture line glow before the capture comes.",
    "{piece} turns defense into damage control.",
    "{piece} gives the attack a new address.",
    "{piece} moves like a glitch in the search tree.",
    "{piece} finds the one square that makes the board nervous.",
    "{piece} makes material count less than momentum.",
    "{piece} takes the square and dares the recapture.",
    "{piece} walks into contact and comes out louder.",
    "{piece} tightens the net one file at a time.",
    "{piece} makes the back rank feel watched.",
    "{piece} carries a threat the board cannot hide.",
    "{piece} turns a legal move into a cinematic problem.",
    "{piece} finds the lever and pulls the position open.",
    "{piece} makes the engine spend time it wanted to save.",
    "{piece} lands where the defender least wants a witness.",
    "{piece} bends the tempo until something cracks.",
    "{piece} enters the pocket between courage and mistake.",
    "{piece} forces the next move to explain itself.",
    "{piece} makes pressure visible.",
    "{piece} brings the attack into speaking distance.",
    "{piece} turns the board state into a chase scene.",
    "{piece} steps forward and the safe squares shrink.",
    "{piece} makes the tactic look inevitable in hindsight.",
    "{piece} takes the initiative and leaves the receipt burning.",
    "{piece} moves like it has already seen the ending.",
]

assert len(PHRASE_TEMPLATES) == 100


def build_manifest() -> dict:
    samples = []
    for atom in SIDES:
        samples.append({
            "id": atom["id"],
            "text": atom["text"],
            "category": atom["category"],
            "role": "atom",
            "path": f"atoms/{atom['id']}.ogg",
        })
    for piece in PIECES:
        samples.append({
            "id": f"piece_{piece}",
            "text": piece,
            "category": "piece_atom",
            "role": "atom",
            "piece": piece,
            "path": f"atoms/piece_{piece}.ogg",
        })
    for idx, template in enumerate(PHRASE_TEMPLATES):
        samples.append({
            "id": f"phrase_{idx:03d}",
            "template": template,
            "category": "commentary_phrase_template",
            "role": "template",
            "path_template": f"phrases/{{piece}}/phrase_{idx:03d}.ogg",
        })
    return {
        "schema_version": 1,
        "concept": "game-style reusable chess commentary samples",
        "assembly_examples": [
            ["black_possessive", "phrases/knight/phrase_000.ogg"],
            ["white_possessive", "phrases/queen/phrase_052.ogg"],
        ],
        "pieces": PIECES,
        "sample_count_if_expanded": len(SIDES) + len(PIECES) + len(PHRASE_TEMPLATES) * len(PIECES),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("assets/voice_bank/manifest.json"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()

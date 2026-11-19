#!/usr/bin/env python3
"""Sudoku: a fast solver and a generator of puzzles with exactly one solution. One file, no dependencies.

  python3 sudoku.py new --level hard          make a puzzle (easy | medium | hard | expert)
  python3 sudoku.py play --level medium       play in the terminal, with hints
  python3 sudoku.py html sheet.html --count 6 printable worksheet (add --answers for a key)
  python3 sudoku.py new --seed 42 --solution  same puzzle every time, and show the answer
  python3 sudoku.py solve "8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4.."
  python3 sudoku.py --test                    run the built-in tests

MIT License, Copyright (c) 2026.
"""
import argparse, random, sys, time

FULL = 0x3FE  # bits 1..9 set


def _solve(grid, limit, rnd=None):
    """Backtracking with bitmasks, always filling the most constrained cell first.
    Returns (solutions found, up to `limit`; search nodes; guesses made). Bad givens give no solutions."""
    g = list(grid)
    rows, cols, boxes = [0] * 9, [0] * 9, [0] * 9
    for i, v in enumerate(g):
        if v:
            b, r, c = 1 << v, i // 9, i % 9
            k = r // 3 * 3 + c // 3
            if rows[r] & b or cols[c] & b or boxes[k] & b:
                return [], 0, 0
            rows[r] |= b; cols[c] |= b; boxes[k] |= b
    sols, nodes, guesses = [], [0], [0]

    def rec():
        nodes[0] += 1
        best, bm, bn = -1, 0, 10
        for i in range(81):
            if g[i] == 0:
                r, c = divmod(i, 9)
                m = FULL & ~(rows[r] | cols[c] | boxes[r // 3 * 3 + c // 3])
                n = m.bit_count()
                if n < bn:
                    best, bm, bn = i, m, n
                    if n <= 1:
                        break
        if best < 0:
            sols.append(g[:])
            return len(sols) >= limit
        if bn > 1:
            guesses[0] += 1
        r, c = divmod(best, 9)
        k = r // 3 * 3 + c // 3
        vals = [v for v in range(1, 10) if bm >> v & 1]
        if rnd:
            rnd.shuffle(vals)
        for v in vals:
            b = 1 << v
            g[best] = v; rows[r] |= b; cols[c] |= b; boxes[k] |= b
            if rec():
                return True
            rows[r] ^= b; cols[c] ^= b; boxes[k] ^= b; g[best] = 0
        return False

    rec()
    return sols, nodes[0], guesses[0]


CLUES = {"easy": 40, "medium": 31, "hard": 27, "expert": 23}  # clue counts to aim for
LEVELS = list(CLUES)
UNITS = ([(f"row {'ABCDEFGHI'[r]}", [r * 9 + c for c in range(9)]) for r in range(9)]
         + [(f"column {c + 1}", [r * 9 + c for r in range(9)]) for c in range(9)]
         + [(f"box {br * 3 + bc + 1}", [(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)]) for br in range(3) for bc in range(3)])


def cell_name(i):
    return "ABCDEFGHI"[i // 9] + str(i % 9 + 1)


def _cands(g):
    """Bitmask of possible digits for every empty cell (0 for filled cells)."""
    used = {}
    for name, cells in UNITS:
        m = 0
        for i in cells:
            m |= 1 << g[i] if g[i] else 0
        used[name] = m
    out = [0] * 81
    for i in range(81):
        if g[i] == 0:
            r, c = divmod(i, 9)
            out[i] = FULL & ~(used[f"row {'ABCDEFGHI'[r]}"] | used[f"column {c + 1}"] | used[f"box {r // 3 * 3 + c // 3 + 1}"])
    return out


def logic_solve(grid):
    """Solve like a person: naked singles (a cell with one candidate), then hidden singles
    (a digit with one place in a row/column/box). Returns (grid, steps); steps are (cell, digit, why)."""
    g, steps = list(grid), []
    while True:
        cand, move = _cands(g), None
        for i in range(81):
            if g[i] == 0 and cand[i].bit_count() == 1:
                move = (i, cand[i].bit_length() - 1, "naked")
                break
        if not move:
            for name, cells in UNITS:
                for v in range(1, 10):
                    spots = [i for i in cells if g[i] == 0 and cand[i] >> v & 1]
                    if len(spots) == 1:
                        move = (spots[0], v, name)
                        break
                if move:
                    break
        if not move:
            return g, steps
        g[move[0]] = move[1]
        steps.append(move)


def rate(puz):
    """easy: naked singles are enough. medium: needs hidden singles. hard / expert: logic alone gets stuck and the
    solver has to guess (up to 12 guesses = hard, more = expert)."""
    g, steps = logic_solve(puz)
    if all(g):
        return "medium" if any(s[2] != "naked" for s in steps) else "easy"
    return "hard" if _solve(puz, 2)[2] <= 12 else "expert"


def _make(level, rnd):
    full = _solve([0] * 81, 1, rnd)[0][0]
    puz, clues = full[:], 81
    cells = list(range(81))
    rnd.shuffle(cells)
    for i in cells:
        if clues <= CLUES[level]:
            break
        keep, puz[i] = puz[i], 0
        if len(_solve(puz, 2)[0]) == 1:
            clues -= 1
        else:
            puz[i] = keep
    return puz, full


def generate(level="medium", seed=None, tries=300):
    """Returns (puzzle, solution) with exactly one solution and a difficulty rating equal to `level`
    (if no puzzle of that exact rating turns up in `tries` attempts, the closest one is returned)."""
    rnd = random.Random(seed)
    best = None
    for _ in range(tries):
        puz, full = _make(level, rnd)
        if rate(puz) == level:
            return puz, full
        best = best or (puz, full)
    return best


def parse(text):
    s = [c for c in text if not c.isspace()]
    if len(s) != 81 or any(c not in "0123456789." for c in s):
        raise ValueError("a puzzle is 81 characters: digits 1-9, and . or 0 for empty cells")
    return [0 if c in ".0" else int(c) for c in s]


def show(g):
    sep = "+-------+-------+-------+"
    out = [sep]
    for r in range(9):
        row = "".join(("| " if c % 3 == 0 else "") + (str(g[r * 9 + c]) if g[r * 9 + c] else ".") + " " for c in range(9))
        out += [row + "|"] + ([sep] if r % 3 == 2 else [])
    return "\n".join(out)


def valid_solution(g):
    ok = set(range(1, 10))
    units = [[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)]
    units += [[(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)] for br in range(3) for bc in range(3)]
    return all({g[i] for i in u} == ok for u in units)


def hint_for(g):
    g2, steps = logic_solve(g)
    if not steps:
        return None
    i, v, why = steps[0]
    if why == "naked":
        return i, v, f"{cell_name(i)} can only be {v}: every other digit is already in its row, column or box."
    return i, v, f"In {why}, the digit {v} has only one place left: {cell_name(i)}."


def play(level="medium", seed=None, inp=input, out=print):
    puz, sol = generate(level, seed)
    g, hist, hints, t0 = puz[:], [], 0, time.time()
    color = sys.stdout.isatty()
    show_board = lambda: out("    1 2 3   4 5 6   7 8 9\n" + "\n".join(
        ("  +-------+-------+-------+\n" if r % 3 == 0 else "") + "ABCDEFGHI"[r] + " | " + " | ".join(
            " ".join((("\033[34m%d\033[0m" if color and not puz[r * 9 + c] else "%d") % g[r * 9 + c] if g[r * 9 + c] else ".") for c in range(b, b + 3))
            for b in (0, 3, 6)) + " |" for r in range(9)) + "\n  +-------+-------+-------+")
    out(f"{level} puzzle ({sum(1 for v in puz if v)} clues). Type 'help' for commands.")
    while True:
        show_board()
        if g == sol:
            m, s = divmod(int(time.time() - t0), 60)
            out(f"Solved! {m}:{s:02d}, {hints} hint{'s' if hints != 1 else ''}.")
            return True
        try:
            line = inp("> ").strip().lower()
        except EOFError:
            return False
        w = line.split()
        if not w:
            continue
        if w[0] in ("quit", "q", "exit"):
            return False
        if w[0] == "help":
            out("a1 5  put 5 in row A, column 1   |  a1 0  clear it   |  hint  |  check  |  undo  |  solve  |  quit")
        elif w[0] == "undo":
            if hist:
                i, old = hist.pop()
                g[i] = old
            else:
                out("Nothing to undo.")
        elif w[0] == "check":
            bad = [cell_name(i) for i in range(81) if g[i] and g[i] != sol[i]]
            out("Wrong: " + ", ".join(bad) if bad else "Everything you have entered so far is correct.")
        elif w[0] == "hint":
            if any(g[i] and g[i] != sol[i] for i in range(81)):
                out("Some entries are wrong. Type 'check' to find them first.")
                continue
            hnt = hint_for(g)
            hints += 1
            if hnt:
                out("Hint: " + hnt[2])
            else:
                i = next(i for i in range(81) if not g[i])
                out(f"No simple deduction here. Try {cell_name(i)} = {sol[i]}.")
        elif w[0] == "solve":
            g = sol[:]
            out("Solution:")
        elif len(w[0]) == 2 and w[0][0] in "abcdefghi" and w[0][1] in "123456789":
            i = "abcdefghi".index(w[0][0]) * 9 + int(w[0][1]) - 1
            v = w[1] if len(w) > 1 else ""
            if puz[i]:
                out(f"{cell_name(i)} is a given and can't be changed.")
            elif v in list("0123456789") and len(v) == 1:
                hist.append((i, g[i]))
                g[i] = int(v)
            else:
                out("Use a digit 1-9 (or 0 to clear), like: a1 5")
        else:
            out("Unknown command. Type 'help'.")


def html_page(count, level, seed, answers):
    css = ("body{font-family:system-ui,sans-serif}.p{page-break-inside:avoid;margin:0 auto 32px;width:340px}table{border-collapse:collapse;margin:auto}"
           "td{width:36px;height:36px;border:1px solid #888;text-align:center;font-size:22px}td.g{font-weight:700}"
           "tr:nth-child(3n) td{border-bottom:3px solid #000}tr:first-child td{border-top:3px solid #000}"
           "td:nth-child(3n){border-right:3px solid #000}td:first-child{border-left:3px solid #000}h2{text-align:center;font-size:16px}"
           "@media print{.pg{page-break-after:always}}")
    table = lambda g, given: "<table>" + "".join("<tr>" + "".join(f"<td class='g'>{g[r*9+c]}</td>" if given[r*9+c] else f"<td>{g[r*9+c] or ''}</td>" for c in range(9)) + "</tr>" for r in range(9)) + "</table>"
    puzzles = [generate(level, None if seed is None else seed + k) for k in range(count)]
    body = "".join(f"<div class='p'><h2>Puzzle {k + 1} ({level})</h2>{table(p, p)}</div>" for k, (p, s) in enumerate(puzzles))
    if answers:
        body += "<h1 style='text-align:center'>Answers</h1>" + "".join(f"<div class='p'><h2>Puzzle {k + 1}</h2>{table(s, p)}</div>" for k, (p, s) in enumerate(puzzles))
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Sudoku worksheet</title><style>{css}</style></head><body>{body}</body></html>"


def self_test():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("  FAIL:", name)

    hardest = parse("8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..")
    t = time.time()
    sols, nodes, _ = _solve(hardest, 2)
    ms = (time.time() - t) * 1000
    check("a famously hard puzzle has exactly one solution", len(sols) == 1)
    check("that solution is valid and keeps the givens", valid_solution(sols[0]) and all(a == 0 or a == b for a, b in zip(hardest, sols[0])))
    check("it is the known answer", "".join(map(str, sols[0])) == "812753649943682175675491283154237896369845721287169534521974368438526917796318452")
    print(f"  hardest puzzle solved in {ms:.0f} ms ({nodes:,} search nodes)")
    check("conflicting givens are rejected", _solve(parse("55" + "." * 79), 1)[0] == [])
    check("an empty grid has many solutions (stops at the limit)", len(_solve([0] * 81, 2)[0]) == 2)
    check("a contradictory puzzle has no solution", _solve(parse("12345678." + "." * 8 + "9" + "." * 63), 1)[0] == [])
    full = _solve([0] * 81, 1, random.Random(1))[0][0]
    check("random full grids are valid", valid_solution(full))
    check("a solved grid solves to itself", _solve(full, 2)[0] == [full])
    for level, target in CLUES.items():
        for seed in range(4):
            puz, sol = generate(level, seed)
            clues = sum(1 for v in puz if v)
            found = _solve(puz, 2)[0]
            check(f"{level} seed {seed}: unique solution", len(found) == 1 and found[0] == sol)
            check(f"{level} seed {seed}: valid, clue count {clues} close to {target}", valid_solution(sol) and target <= clues <= target + 6)
    for level in LEVELS:
        for seed in range(3):
            puz, sol = generate(level, seed)
            check(f"rating of a generated {level} puzzle (seed {seed}) is {level}", rate(puz) == level)
    easy = generate("easy", 1)[0]
    g, steps = logic_solve(easy)
    check("easy puzzles are solved by logic alone", all(g) and valid_solution(g) and all(s[2] == "naked" for s in steps))
    hard = generate("hard", 1)[0]
    g, _ = logic_solve(hard)
    check("hard puzzles leave logic stuck", not all(g))
    puz, sol = generate("medium", 2)
    h1 = hint_for(puz)
    check("a hint is a correct deduction", h1 is not None and sol[h1[0]] == h1[1])
    moves, seen_ok = [], True
    for i in range(81):
        if not puz[i]:
            moves.append(f"{cell_name(i).lower()} {sol[i]}")
    script = iter(["help", "a1 x", "check", "hint"] + moves)
    log = []
    def fake(prompt):
        try:
            return next(script)
        except StopIteration:
            raise EOFError
    check("scripted game is won", play("medium", 2, inp=fake, out=log.append) is True and any("Solved!" in str(x) for x in log))
    log2 = []
    wrong = iter(["a1 1", "a2 1", "check", "undo", "undo", "check", "solve"])
    play("easy", 3, inp=lambda _: next(wrong, "quit"), out=log2.append)
    check("check finds wrong entries and undo removes them", any("Wrong" in str(x) for x in log2) and any("correct" in str(x) for x in log2))
    page = html_page(3, "easy", 5, True)
    check("worksheet has 3 puzzles and 3 answers", page.count("<table>") == 6 and "Answers" in page and page.startswith("<!DOCTYPE html>"))
    check("same seed gives the same puzzle", generate("hard", 5) == generate("hard", 5))
    check("different seeds give different puzzles", generate("hard", 5)[0] != generate("hard", 6)[0])
    check("show() has 13 lines", len(show(hardest).splitlines()) == 13)
    try:
        parse("123")
        check("short input is rejected", False)
    except ValueError:
        check("short input is rejected", True)
    print(f"{passed}/{passed + failed} checks passed")
    return failed == 0


def main():
    ap = argparse.ArgumentParser(description="Sudoku generator and solver")
    ap.add_argument("--test", action="store_true", help="run the built-in tests")
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("new", help="generate a puzzle")
    n.add_argument("--level", choices=LEVELS, default="medium")
    n.add_argument("--seed", type=int)
    n.add_argument("--solution", action="store_true", help="also print the solution")
    pl = sub.add_parser("play", help="play in the terminal")
    pl.add_argument("--level", choices=LEVELS, default="medium")
    pl.add_argument("--seed", type=int)
    hp = sub.add_parser("html", help="write a printable worksheet")
    hp.add_argument("file")
    hp.add_argument("--level", choices=LEVELS, default="medium")
    hp.add_argument("--count", type=int, default=4)
    hp.add_argument("--seed", type=int)
    hp.add_argument("--answers", action="store_true", help="add an answer key at the end")
    s = sub.add_parser("solve", help="solve a puzzle (81 characters; read from stdin if omitted)")
    s.add_argument("puzzle", nargs="?")
    a = ap.parse_args()
    if a.test:
        sys.exit(0 if self_test() else 1)
    if a.cmd == "new":
        puz, sol = generate(a.level, a.seed)
        print(f"{a.level} puzzle ({rate(puz)} by logic), {sum(1 for v in puz if v)} clues, exactly one solution\n{show(puz)}\n{''.join(str(v or '.') for v in puz)}")
        if a.solution:
            print("\nsolution\n" + show(sol))
    elif a.cmd == "play":
        play(a.level, a.seed)
    elif a.cmd == "html":
        with open(a.file, "w", encoding="utf-8") as f:
            f.write(html_page(max(1, a.count), a.level, a.seed, a.answers))
        print(f"wrote {a.file} ({a.count} {a.level} puzzles{' with answers' if a.answers else ''}); open it in a browser and print")
    elif a.cmd == "solve":
        try:
            puz = parse(a.puzzle if a.puzzle else sys.stdin.read())
        except ValueError as e:
            sys.exit(f"error: {e}")
        sols, nodes, _ = _solve(puz, 2)
        if not sols:
            sys.exit("no solution: the givens contradict each other")
        print(show(sols[0]))
        print(f"unique solution, {nodes:,} search nodes" if len(sols) == 1 else "warning: this puzzle has more than one solution; showing the first")
    else:
        ap.print_help()


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # e.g. `sudoku.py new | head`: the reader left early, which is fine
        sys.stderr.close()

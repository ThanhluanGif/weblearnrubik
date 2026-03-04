from __future__ import annotations

from collections import Counter
from itertools import product
from pathlib import Path

from flask import Flask, request

try:
    import kociemba
except ImportError:  # pragma: no cover - handled at runtime for user guidance
    kociemba = None


FACE_ORDER = ["U", "R", "F", "D", "L", "B"]
ROTATE_CW_INDEX = [6, 3, 0, 7, 4, 1, 8, 5, 2]
FACE_NAME_VI = {
    "U": "Tren",
    "R": "Phai",
    "F": "Truoc",
    "D": "Duoi",
    "L": "Trai",
    "B": "Sau",
}

APP_ROOT = Path(__file__).parent
WEB_ROOT = APP_ROOT / "web"

app = Flask(__name__, static_folder=str(WEB_ROOT), static_url_path="")


def rotate_face(facelets: list[str], turns: int) -> list[str]:
    rotated = facelets[:]
    for _ in range(turns % 4):
        rotated = [rotated[idx] for idx in ROTATE_CW_INDEX]
    return rotated


def normalize_state(raw_state: str) -> str:
    return "".join(raw_state.split()).upper()


def validate_state(state: str) -> str | None:
    if len(state) != 54:
        return "Chuoi trang thai phai co dung 54 ky tu."

    invalid_chars = sorted(set(state) - set(FACE_ORDER))
    if invalid_chars:
        return f"Trang thai chi duoc chua ky tu U R F D L B. Gap: {' '.join(invalid_chars)}"

    counts = Counter(state)
    bad_counts = [face for face in FACE_ORDER if counts.get(face, 0) != 9]
    if bad_counts:
        detail = ", ".join(f"{face}={counts.get(face, 0)}" for face in FACE_ORDER)
        return f"Moi ky tu U R F D L B phai xuat hien 9 lan. Hien tai: {detail}"

    return None


def describe_move(move: str) -> str:
    face = move[0]
    suffix = move[1:]
    face_name = FACE_NAME_VI.get(face, face)

    if suffix == "2":
        action = "Xoay 180 do"
    elif suffix == "'":
        action = "Xoay 90 do nguoc chieu kim dong ho"
    else:
        action = "Xoay 90 do theo chieu kim dong ho"

    return f"{action} mat {face_name} ({move})"


def solve_state(state: str) -> str:
    if kociemba is None:
        raise RuntimeError(
            "Chua cai thu vien kociemba. Hay chay: pip install -r requirements.txt"
        )

    return kociemba.solve(state)


def solve_from_faces(
    faces: dict[str, list[str]], max_attempts: int = 4096
) -> tuple[str, str, dict[str, int], int]:
    for face in FACE_ORDER:
        if face not in faces:
            raise ValueError(f"Thieu mat {face}. Can du 6 mat U,R,F,D,L,B.")
        if len(faces[face]) != 9:
            raise ValueError(f"Mat {face} phai co dung 9 o.")

    normalized_faces: dict[str, list[str]] = {}
    for face in FACE_ORDER:
        normalized_faces[face] = [cell.upper() for cell in faces[face]]

    attempts = 0
    last_error = "Khong tim duoc trang thai hop le."

    for turns in product(range(4), repeat=6):
        attempts += 1
        if attempts > max_attempts:
            break

        state_parts: list[str] = []
        for idx, face in enumerate(FACE_ORDER):
            rotated = rotate_face(normalized_faces[face], turns[idx])
            state_parts.extend(rotated)
        state = "".join(state_parts)

        validation_error = validate_state(state)
        if validation_error:
            last_error = validation_error
            continue

        try:
            solution = solve_state(state)
            face_rotations = {face: turns[idx] for idx, face in enumerate(FACE_ORDER)}
            return state, solution, face_rotations, attempts
        except Exception as exc:  # pragma: no cover - relies on solver internals
            last_error = str(exc)
            continue

    raise ValueError(last_error)


def solution_to_steps(solution: str) -> list[dict[str, str]]:
    if not solution.strip():
        return []
    moves = solution.split()
    return [{"move": move, "instruction": describe_move(move)} for move in moves]


@app.get("/api/health")
def api_health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.get("/api/cuboid-guide")
def api_cuboid_guide() -> tuple[dict[str, object], int]:
    return (
        {
            "title": "Huong dan Rubik khoi chu nhat (cuboid)",
            "note": (
                "Che do camera + giai tu dong hien tai danh cho 3x3. "
                "Voi cuboid, ban co the lam theo reduction method ben duoi."
            ),
            "steps": [
                "Xac dinh loai khoi (vi du 2x2x3, 3x3x2, 4x4x2) va quy uoc mat U, D, F.",
                "Ghep cac cap canh de dua khoi ve trang thai gan voi 3x3 (reduction).",
                "Giai nhu Rubik 3x3: tao cross, xep goc/canh lop dau, sau do lop cuoi.",
                "Neu gap parity cua khoi chan/cuboid, ap dung thuat toan parity tuong ung.",
            ],
            "example_algs": [
                {
                    "name": "Mau chu trinh co ban de luyen tay",
                    "sequence": "R U R' U'",
                },
                {
                    "name": "Mau doi cho 3 goc",
                    "sequence": "U R U' L' U R' U' L",
                },
            ],
        },
        200,
    )


@app.post("/api/solve-3x3")
def api_solve_3x3() -> tuple[dict[str, object], int]:
    payload = request.get_json(silent=True) or {}

    try:
        if "faces" in payload:
            max_attempts = int(payload.get("maxAttempts", 4096))
            state, solution, rotations, attempts = solve_from_faces(
                payload["faces"], max_attempts=max_attempts
            )
            steps = solution_to_steps(solution)
            return (
                {
                    "mode": "faces",
                    "state": state,
                    "solution": solution,
                    "moveCount": len(solution.split()) if solution.strip() else 0,
                    "steps": steps,
                    "rotations": rotations,
                    "attempts": attempts,
                },
                200,
            )

        state = normalize_state(str(payload.get("state", "")))
        validation_error = validate_state(state)
        if validation_error:
            return {"error": validation_error}, 400

        solution = solve_state(state)
        steps = solution_to_steps(solution)
        return (
            {
                "mode": "state",
                "state": state,
                "solution": solution,
                "moveCount": len(solution.split()) if solution.strip() else 0,
                "steps": steps,
            },
            200,
        )

    except ValueError as exc:
        return {"error": str(exc)}, 400
    except RuntimeError as exc:
        return {"error": str(exc)}, 500
    except Exception as exc:  # pragma: no cover - safety net
        return {"error": f"Khong the giai cube: {exc}"}, 500


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/<path:path>")
def static_proxy(path: str):
    target = WEB_ROOT / path
    if target.exists() and target.is_file():
        return app.send_static_file(path)
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

from __future__ import annotations

from collections import Counter
from itertools import product
from pathlib import Path

from flask import Flask, request

try:
    import kociemba as native_kociemba
except ImportError:  # pragma: no cover - optional dependency
    native_kociemba = None

try:
    from pykociemba import search as pykociemba_search
except ImportError:  # pragma: no cover - optional fallback
    pykociemba_search = None


FACE_ORDER = ["U", "R", "F", "D", "L", "B"]
ROTATE_CW_INDEX = [6, 3, 0, 7, 4, 1, 8, 5, 2]
FACE_NAME_VI = {
    "U": "Trên",
    "R": "Phải",
    "F": "Trước",
    "D": "Dưới",
    "L": "Trái",
    "B": "Sau",
}

APP_ROOT = Path(__file__).parent
WEB_ROOT = APP_ROOT / "web"

KOCIEMBA_ERRORS = {
    "Error 1": "Không có đúng một ô màu cho mỗi màu sắc.",
    "Error 2": "Không đủ 12 viên cạnh hợp lệ (mỗi viên phải xuất hiện đúng 1 lần).",
    "Error 3": "Lỗi lật cạnh: có ít nhất một viên cạnh bị lật sai.",
    "Error 4": "Không đủ 8 viên góc hợp lệ (mỗi viên phải xuất hiện đúng 1 lần).",
    "Error 5": "Lỗi xoay góc: có ít nhất một viên góc bị xoay sai.",
    "Error 6": "Lỗi parity: cần hoán đổi hai góc hoặc hai cạnh để hợp lệ.",
    "Error 7": "Không tìm thấy lời giải trong giới hạn độ sâu đã đặt.",
    "Error 8": "Hết thời gian tìm kiếm lời giải.",
}

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
        return "Chuỗi trạng thái phải có đúng 54 ký tự."

    invalid_chars = sorted(set(state) - set(FACE_ORDER))
    if invalid_chars:
        return f"Trạng thái chỉ được chứa ký tự U R F D L B. Gặp: {' '.join(invalid_chars)}"

    counts = Counter(state)
    bad_counts = [face for face in FACE_ORDER if counts.get(face, 0) != 9]
    if bad_counts:
        detail = ", ".join(f"{face}={counts.get(face, 0)}" for face in FACE_ORDER)
        return f"Mỗi ký tự U R F D L B phải xuất hiện 9 lần. Hiện tại: {detail}"

    return None


def describe_move(move: str) -> str:
    face = move[0]
    suffix = move[1:]
    face_name = FACE_NAME_VI.get(face, face)

    if suffix == "2":
        action = "Xoay 180 độ"
    elif suffix == "'":
        action = "Xoay 90 độ ngược chiều kim đồng hồ"
    else:
        action = "Xoay 90 độ theo chiều kim đồng hồ"

    return f"{action} mặt {face_name} ({move})"


def solve_state(state: str) -> str:
    if native_kociemba is not None:
        return native_kociemba.solve(state)

    if pykociemba_search is None:
        raise RuntimeError("Chưa có solver. Hãy chạy: pip install -r requirements.txt")

    result = pykociemba_search.Search().solution(state, 24, 1000, False).strip()
    if result in KOCIEMBA_ERRORS:
        raise ValueError(KOCIEMBA_ERRORS[result])
    return result


def solve_from_faces(
    faces: dict[str, list[str]], max_attempts: int = 4096
) -> tuple[str, str, dict[str, int], int]:
    for face in FACE_ORDER:
        if face not in faces:
            raise ValueError(f"Thiếu mặt {face}. Cần đủ 6 mặt U,R,F,D,L,B.")
        if len(faces[face]) != 9:
            raise ValueError(f"Mặt {face} phải có đúng 9 ô.")

    normalized_faces: dict[str, list[str]] = {}
    for face in FACE_ORDER:
        normalized_faces[face] = [cell.upper() for cell in faces[face]]

    attempts = 0
    last_error = "Không tìm được trạng thái hợp lệ."

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
            "title": "Hướng dẫn Rubik khối chữ nhật",
            "note": (
                "Chế độ camera + giải tự động hiện tại dành cho 3x3. "
                "Với Rubik khối chữ nhật, bạn có thể làm theo phương pháp reduction bên dưới."
            ),
            "steps": [
                "Xác định loại khối (ví dụ 2x2x3, 3x3x2, 4x4x2) và quy ước mặt U, D, F.",
                "Ghép các cặp cạnh để đưa khối về trạng thái gần với 3x3 (reduction).",
                "Giải như Rubik 3x3: tạo dấu cộng, xếp góc/cạnh lớp đầu, sau đó lớp cuối.",
                "Nếu gặp parity của khối chẵn/cuboid, áp dụng thuật toán parity tương ứng.",
            ],
            "example_algs": [
                {
                    "name": "Mẫu chu trình cơ bản để luyện tay",
                    "sequence": "R U R' U'",
                },
                {
                    "name": "Mẫu đổi chỗ 3 góc",
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
        return {"error": f"Không thể giải khối Rubik: {exc}"}, 500


@app.errorhandler(404)
def api_not_found(error):
    if request.path.startswith("/api/"):
        return {"error": "Không tìm thấy đường dẫn API."}, 404
    return error


@app.errorhandler(405)
def api_method_not_allowed(error):
    if request.path.startswith("/api/"):
        return {"error": "Phương thức yêu cầu không được hỗ trợ."}, 405
    return error


@app.errorhandler(500)
def api_internal_error(error):
    if request.path.startswith("/api/"):
        return {"error": "Máy chủ đang gặp lỗi nội bộ."}, 500
    return error


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

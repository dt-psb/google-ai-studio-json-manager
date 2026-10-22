#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google AI Studio JSON Manager - Local Server
============================================
경량 로컬 HTTP 서버. JSON 파일 저장/로드, 브랜치 분석, 폰트 업로드 API를 제공합니다.

실행: python server.py  (또는 run.bat 더블클릭)
접속: http://localhost:8500/index.html
"""

import base64
import copy
import difflib
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import time
import traceback
import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 전역 설정 상수
# ---------------------------------------------------------------------------
DEFAULT_PORT = 8500
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
SETTINGS_FILE = os.path.join(BASE_DIR, "app_settings.json")
WORLDVIEWS_FILE = os.path.join(BASE_DIR, "worldviews_config.json")
FONT_EXTENSIONS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}
PREVIEW_MAX_LEN = 90
FUZZY_TEXT_SAMPLE = 600

os.makedirs(STORAGE_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 앱 전역 설정(테마 등) I/O
# ---------------------------------------------------------------------------

DEFAULT_APP_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
}

def load_app_settings() -> Dict[str, Any]:
    """app_settings.json에서 테마 등 전역 설정을 읽어 반환."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = DEFAULT_APP_SETTINGS.copy()
                merged.update(data)
                return merged
        except Exception:
            pass
    return DEFAULT_APP_SETTINGS.copy()

def save_app_settings(data: Dict[str, Any]) -> bool:
    """app_settings.json에 테마 등 전역 설정을 영구 저장."""
    try:
        current = load_app_settings()
        if isinstance(data, dict):
            current.update(data)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Error] app settings 저장 실패: {e}")
        return False

# ---------------------------------------------------------------------------
# 윈도우 OS 시스템 클립보드 다이렉트 고속 복사 (대용량 3~10MB JSON 완벽 지원)
# ---------------------------------------------------------------------------

def set_windows_clipboard_text(text: str) -> bool:
    """Windows Win32 API를 직접 호출하여 대용량 텍스트를 시스템 클립보드에 초고속 복사."""
    if not isinstance(text, str):
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 64비트 Windows 포인터 호환 타입 정의
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.CloseClipboard.restype = wintypes.BOOL

        GMEM_MOVEABLE = 0x0002
        CF_UNICODETEXT = 13

        encoded = text.encode("utf-16le") + b"\x00\x00"

        # 클립보드 열기 시도 (최대 20회 재시도, 0.6초)
        opened = False
        for _ in range(20):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.03)

        if not opened:
            err = ctypes.GetLastError()
            print(f"[Warning] Windows OpenClipboard failed (LastError: {err})")
            return False

        try:
            user32.EmptyClipboard()
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                print(f"[Warning] Windows GlobalAlloc failed for {len(encoded)} bytes")
                return False

            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                kernel32.GlobalFree(h_mem)
                print("[Warning] Windows GlobalLock failed")
                return False

            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)

            if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                err = ctypes.GetLastError()
                kernel32.GlobalFree(h_mem)
                print(f"[Warning] Windows SetClipboardData failed (LastError: {err})")
                return False
            return True
        finally:
            user32.CloseClipboard()
    except Exception as e:
        print(f"[Error] Windows 클립보드 복사 예외: {e}\n{traceback.format_exc()}")
        return False

# ---------------------------------------------------------------------------
# 세계관(Worldview) 설정 I/O
# ---------------------------------------------------------------------------

DEFAULT_WORLDVIEWS_CONFIG: Dict[str, Any] = {
    "worldviews": ["세계관 1", "세계관 2", "세계관 3"],
    "mappings": {},
}


def load_worldviews_config() -> Dict[str, Any]:
    """worldviews_config.json을 읽어 반환. 없거나 파싱 실패 시 기본값 반환."""
    if os.path.exists(WORLDVIEWS_FILE):
        try:
            with open(WORLDVIEWS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("worldviews", DEFAULT_WORLDVIEWS_CONFIG["worldviews"][:])
                data.setdefault("mappings", {})
                if not isinstance(data["worldviews"], list):
                    data["worldviews"] = DEFAULT_WORLDVIEWS_CONFIG["worldviews"][:]
                if not isinstance(data["mappings"], dict):
                    data["mappings"] = {}
                return data
        except Exception:
            pass
    return {k: v.copy() if isinstance(v, (dict, list)) else v
            for k, v in DEFAULT_WORLDVIEWS_CONFIG.items()}


def save_worldviews_config(data: Dict[str, Any]) -> bool:
    """worldviews_config.json에 data를 저장. 성공 시 True."""
    try:
        with open(WORLDVIEWS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Error] worldviews config 저장 실패: {e}")
        return False


# ---------------------------------------------------------------------------
# 유틸리티 함수
# ---------------------------------------------------------------------------

def format_size(num_bytes: int) -> str:
    """바이트를 사람이 읽기 쉬운 크기 문자열로 변환 (예: 1.5 KB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024.0:
            return f"{int(num_bytes)} B" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def is_safe_path(base: str, path: str) -> bool:
    """path가 base 디렉터리 내부에 있는지 검사 (Path Traversal 방지)."""
    base = os.path.abspath(base)
    resolved = os.path.abspath(os.path.join(base, path))
    try:
        return os.path.commonpath([base, resolved]) == base
    except ValueError:
        return False


def get_file_stat(filepath: str) -> Optional[Dict[str, Any]]:
    """파일 stat 정보를 딕셔너리로 반환. 실패 시 None."""
    try:
        st = os.stat(filepath)
        return {"size": st.st_size, "size_formatted": format_size(st.st_size), "mtime": st.st_mtime}
    except Exception:
        return None


def normalize_path(path: str) -> str:
    """백슬래시를 슬래시로 통일하고 앞뒤 공백을 제거."""
    return path.replace("\\", "/").strip()


def strip_storage_prefix(path: str) -> str:
    """'storage/' 접두어가 있으면 제거."""
    clean = normalize_path(path)
    return clean[len("storage/"):] if clean.startswith("storage/") else clean


def get_font_format(ext: str) -> str:
    """파일 확장자(소문자, 점 포함)에 해당하는 폰트 포맷 문자열 반환."""
    return FONT_EXTENSIONS.get(ext.lower(), "opentype")


# ---------------------------------------------------------------------------
# 스토리지 트리 / 파일 목록
# ---------------------------------------------------------------------------

def get_storage_tree(dir_path: str, rel_path: str = "") -> Dict[str, Any]:
    """storage/ 디렉터리를 재귀 탐색하여 폴더·파일 트리를 반환하고 모든 하위 문서 개수까지 계산."""
    tree: Dict[str, Any] = {
        "name": os.path.basename(dir_path) if rel_path else "storage",
        "path": normalize_path(rel_path),
        "folders": [],
        "files": [],
        "direct_files_count": 0,
        "total_files_count": 0,
    }
    if not os.path.exists(dir_path):
        return tree

    try:
        entries = sorted(os.listdir(dir_path))
    except Exception:
        return tree

    for entry in entries:
        full_path = os.path.join(dir_path, entry)
        sub_rel = normalize_path(os.path.join(rel_path, entry) if rel_path else entry)

        if os.path.isdir(full_path):
            if not entry.startswith(".") and entry != "__pycache__":
                sub_tree = get_storage_tree(full_path, sub_rel)
                tree["folders"].append(sub_tree)
        elif os.path.isfile(full_path) and is_valid_json_file(full_path, entry):
            stat = get_file_stat(full_path)
            if stat:
                tree["files"].append({"name": entry, "path": sub_rel, **stat})

    # 직속 파일 수 및 모든 하위 폴더(이중, 삼중, 다중 계층) 내 파일 총합 재귀 계산
    direct_count = len(tree["files"])
    sub_total = sum(f.get("total_files_count", 0) for f in tree["folders"])
    tree["direct_files_count"] = direct_count
    tree["total_files_count"] = direct_count + sub_total

    return tree


def get_root_json_files() -> List[Dict[str, Any]]:
    """BASE_DIR 루트에 있는 유효한 JSON 파일 목록을 반환 (mtime 내림차순)."""
    root_files = []
    for filename in os.listdir(BASE_DIR):
        full_path = os.path.join(BASE_DIR, filename)
        if os.path.isfile(full_path) and is_valid_json_file(full_path, filename):
            stat = get_file_stat(full_path)
            if stat:
                root_files.append({"name": filename, "path": filename, "is_root": True, **stat})
    root_files.sort(key=lambda x: x["mtime"], reverse=True)
    return root_files


def get_all_storage_files() -> List[Dict[str, Any]]:
    """storage/ 폴더 내 모든 유효한 JSON 파일을 재귀 탐색하여 반환."""
    if not os.path.exists(STORAGE_DIR):
        return []

    # 세계관 매핑 정보 로드 및 정규화
    wv_cfg = load_worldviews_config()
    norm_mappings = _build_normalized_mappings(wv_cfg.get("mappings", {}))

    results = []
    for root, _dirs, files in os.walk(STORAGE_DIR):
        for filename in files:
            abs_path = normalize_path(os.path.abspath(os.path.join(root, filename)))
            if not is_valid_json_file(abs_path, filename):
                continue

            rel_path = normalize_path(os.path.relpath(abs_path, STORAGE_DIR))
            rel_parts = rel_path.split("/")
            folder = "/".join(rel_parts[:-1]) if len(rel_parts) > 1 else ""
            category = _resolve_category(rel_path, filename, rel_parts, norm_mappings)

            stat = get_file_stat(abs_path)
            if stat:
                results.append({
                    "name": filename,
                    "rel_path": rel_path,
                    "folder": folder,
                    "category": category,
                    "full_path": abs_path,
                    "abs_path": abs_path,
                    **stat,
                })
    return results


# 제외할 시스템/바이너리/스크립트 확장자 목록
EXCLUDED_EXTENSIONS = {
    ".bak", ".tmp", ".swp", ".py", ".pyw", ".pyc", ".bat", ".cmd", ".vbs",
    ".sh", ".exe", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".pdf", ".html", ".htm", ".css",
    ".js", ".ts", ".map", ".db", ".sqlite", ".sqlite3", ".lnk", ".log"
}

_JSON_VALIDITY_CACHE: Dict[str, Tuple[float, int, bool]] = {}


def is_valid_json_file(full_path: str, filename: Optional[str] = None) -> bool:
    """
    확장자가 .json이 아니더라도(확장자가 없거나 .txt 등),
    유효한 JSON 구조이면 True를 반환.
    mtime, size 기반 캐싱을 적용하여 수백 개 파일도 고속으로 판정.
    """
    if filename is None:
        filename = os.path.basename(full_path)

    # 숨김 파일 및 시스템 파일 제외
    if filename.startswith("."):
        return False

    lower = filename.lower()
    _, ext = os.path.splitext(lower)

    # 명백한 비JSON/스크립트/바이너리 제외
    if ext in EXCLUDED_EXTENSIONS or lower.endswith(".bak.json") or lower.endswith(".tmp"):
        return False

    # .json 확장자는 기본 유효
    if lower.endswith(".json"):
        return True

    # 확장자가 없거나 일반 텍스트 파일인 경우: 내용 기반 빠른 유효성 검사
    try:
        st = os.stat(full_path)
        mtime, size = st.st_mtime, st.st_size
        if size < 2 or size > 100 * 1024 * 1024:  # 2바이트 미만(빈파일) 또는 100MB 초과 제외
            return False

        cached = _JSON_VALIDITY_CACHE.get(full_path)
        if cached and cached[0] == mtime and cached[1] == size:
            return cached[2]

        # 첫 2KB를 읽어 공백 제거 후 첫 문자가 { 또는 [ 인지 검사
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(2048).strip()
            if not sample or sample[0] not in ("{", "["):
                _JSON_VALIDITY_CACHE[full_path] = (mtime, size, False)
                return False

        # 끝부분 1KB도 확인하여 마지막 문자가 } 또는 ] 인지 빠른 검사
        try:
            with open(full_path, "rb") as f:
                f.seek(max(0, size - 1024))
                tail_sample = f.read().decode("utf-8", errors="ignore").strip()
                if not tail_sample or tail_sample[-1] not in ("}", "]"):
                    _JSON_VALIDITY_CACHE[full_path] = (mtime, size, False)
                    return False
        except Exception:
            pass

        # 1MB 이하 파일은 json.load로 정밀 검사, 1MB 초과 대용량 파일은 앞뒤 구조가 유효하면 True로 신속 판정하여 지연 제거
        if size <= 1024 * 1024:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                is_valid = isinstance(data, (dict, list))
        else:
            is_valid = True

        _JSON_VALIDITY_CACHE[full_path] = (mtime, size, is_valid)
        return is_valid
    except Exception:
        _JSON_VALIDITY_CACHE[full_path] = (0, 0, False)
        return False


def _is_valid_json_filename(filename: str) -> bool:
    """파일명 기반 1차 판정 (경로를 모를 때 사용)"""
    lower = filename.lower()
    if filename.startswith("."):
        return False
    _, ext = os.path.splitext(lower)
    return ext not in EXCLUDED_EXTENSIONS and not lower.endswith(".bak.json")


def _build_normalized_mappings(mappings: Dict[str, str]) -> Dict[str, str]:
    """매핑 딕셔너리를 다양한 키 형태로 정규화하여 반환."""
    norm: Dict[str, str] = {}
    for key, val in mappings.items():
        clean = normalize_path(str(key))
        basename = os.path.basename(clean)
        for k in (clean, clean.lower(), basename, basename.lower()):
            norm[k] = val
    return norm


def _resolve_category(rel_path: str, filename: str, rel_parts: List[str],
                       norm_mappings: Dict[str, str]) -> str:
    """파일에 해당하는 세계관/카테고리를 반환. 사용자가 지정한 세계관이 없으면 '미분류'."""
    clean_rel = rel_path.lstrip("storage/").lstrip("/")
    for key in (rel_path, rel_path.lower(), clean_rel, clean_rel.lower(), filename, filename.lower(), f"storage/{rel_path}", f"storage/{clean_rel}"):
        if key in norm_mappings:
            return norm_mappings[key]
    return "미분류"


# ---------------------------------------------------------------------------
# 청크 서명 및 유사도 분석
# ---------------------------------------------------------------------------

def extract_chunks_signature(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """JSON 데이터에서 청크 목록을 추출하고 각 청크에 해시·미리보기 등 경량 메타데이터를 부착."""
    chunks_raw = json_data.get("chunkedPrompt", {}).get("chunks", [])
    if not isinstance(chunks_raw, list):
        return []

    result = []
    for i, chunk in enumerate(chunks_raw):
        if not isinstance(chunk, dict):
            continue

        role = chunk.get("role", "user")
        is_thought = bool(chunk.get("isThought", False))
        text, is_thought = _extract_chunk_text(chunk, is_thought)

        norm_text = text.strip()
        role_label = "thought" if is_thought else role
        sig = f"{role}:{'thought' if is_thought else 'normal'}:{norm_text}"

        # 띄어쓰기 정규화 서명
        ws_norm = " ".join(norm_text.split())
        ws_sig = f"{role}:{'thought' if is_thought else 'normal'}:{ws_norm}"

        preview = norm_text.replace("\r", " ").replace("\n", " ").strip()
        if len(preview) > PREVIEW_MAX_LEN:
            preview = preview[:PREVIEW_MAX_LEN - 3] + "..."

        result.append({
            "index": i,
            "role": role_label,
            # 전체 텍스트 대신 퍼지 매칭용 샘플(최대 3000자)만 보관하여 메모리 사용량 90% 이상 절감
            "sample": norm_text[:FUZZY_TEXT_SAMPLE],
            "hash": hashlib.sha256(sig.encode("utf-8")).hexdigest()[:16],
            "ws_hash": hashlib.sha256(ws_sig.encode("utf-8")).hexdigest()[:16],
            "preview": preview,
            "length": len(norm_text),
        })
    return result


def _extract_chunk_text(chunk: Dict[str, Any], is_thought: bool) -> Tuple[str, bool]:
    """청크에서 텍스트를 추출. parts 필드도 처리."""
    text = chunk.get("text", "")
    if not text and isinstance(chunk.get("parts"), list):
        parts_texts = []
        for part in chunk["parts"]:
            if isinstance(part, dict):
                if part.get("thought", False):
                    is_thought = True
                parts_texts.append(part.get("text", ""))
        text = "".join(parts_texts)
    return text, is_thought


# 퍼지 유사도 계산 캐시 (hash쌍 -> ratio)
_CHUNK_SIMILARITY_CACHE: Dict[Tuple[str, str], float] = {}

def are_chunks_similar(c1: Dict, c2: Dict, threshold: float = 0.85) -> Tuple[bool, float, str]:
    """두 청크의 유사도를 계산. 서명 키가 없어도 안전하게 처리. (is_match, ratio, match_type) 반환."""
    r1 = c1.get("role", "user")
    r2 = c2.get("role", "user")
    if r1 != r2:
        return False, 0.0, "role_mismatch"

    h1, h2 = c1.get("hash"), c2.get("hash")
    if h1 and h2 and h1 == h2:
        return True, 1.0, "exact"

    ws1, ws2 = c1.get("ws_hash"), c2.get("ws_hash")
    if ws1 and ws2 and ws1 == ws2:
        return True, 0.999, "whitespace_only"

    s1 = c1.get("sample") or c1.get("text") or ""
    s2 = c2.get("sample") or c2.get("text") or ""

    if s1 == s2:
        return True, 1.0, "exact"

    l1 = c1.get("length", len(s1))
    l2 = c2.get("length", len(s2))
    max_l, min_l = max(l1, l2), min(l1, l2)
    if max_l > 0 and (min_l / max_l) < max(0.5, threshold - 0.20):
        return False, min_l / max_l, "length_diff"

    cache_key = (h1 or s1[:80], h2 or s2[:80])
    if cache_key in _CHUNK_SIMILARITY_CACHE:
        ratio = _CHUNK_SIMILARITY_CACHE[cache_key]
    else:
        sample1 = s1[:FUZZY_TEXT_SAMPLE]
        sample2 = s2[:FUZZY_TEXT_SAMPLE]
        ratio = difflib.SequenceMatcher(None, sample1, sample2).quick_ratio()
        if len(_CHUNK_SIMILARITY_CACHE) > 20000:
            _CHUNK_SIMILARITY_CACHE.clear()
        _CHUNK_SIMILARITY_CACHE[cache_key] = ratio

    if ratio >= threshold:
        return True, ratio, "fuzzy"
    return False, ratio, "different"


def calc_fuzzy_lcp(chunks1: List[Dict], chunks2: List[Dict], threshold: float = 0.85) -> int:
    """두 청크 시퀀스의 최장 공통 접두어(LCP) 길이를 반환."""
    k = 0
    for c1, c2 in zip(chunks1, chunks2):
        match, _, _ = are_chunks_similar(c1, c2, threshold)
        if not match:
            break
        k += 1
    return k


# 별칭 (하위 호환용)
def calc_lcp(chunks1: List[Dict], chunks2: List[Dict]) -> int:
    return calc_fuzzy_lcp(chunks1, chunks2, 0.85)


# ---------------------------------------------------------------------------
# 파일 청크 캐시
# ---------------------------------------------------------------------------

_FILE_CHUNKS_CACHE: Dict[str, Dict[str, Any]] = {}


def get_cached_file_chunks(sf: Dict[str, Any]) -> Tuple[List[Dict], str, str]:
    """파일을 읽어 청크 서명 목록을 반환. mtime 기반 캐싱 적용."""
    path, mtime = sf["abs_path"], sf["mtime"]
    cached = _FILE_CHUNKS_CACHE.get(path)
    if cached and cached["mtime"] == mtime:
        return cached["chunks"], cached["first_prompt"], cached["system_instruction"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = extract_chunks_signature(data)
        first_prompt = next((c["preview"] for c in chunks if c["role"] == "user"), "")
        sys_inst = (data.get("systemInstruction", {}).get("text") or "").strip()[:80]
        _FILE_CHUNKS_CACHE[path] = {
            "mtime": mtime, "chunks": chunks,
            "first_prompt": first_prompt, "system_instruction": sys_inst,
        }
        return chunks, first_prompt, sys_inst
    except Exception:
        return [], "", ""


# ---------------------------------------------------------------------------
# 브랜치 트리 분석 캐시 (스토리지 서명 기반 0ms 고속 응답)
# ---------------------------------------------------------------------------

_BRANCH_TREE_CACHE: Dict[str, Any] = {
    "signature": "",
    "families": [],
    "all_tree_nodes": {},
    "loaded_files": [],
    "categories_list": [],
}


def invalidate_branch_tree_cache():
    """파일 저장/삭제/동기화 시 브랜치 캐시 무효화."""
    _BRANCH_TREE_CACHE["signature"] = ""


# ---------------------------------------------------------------------------
# 브랜치 분석
# ---------------------------------------------------------------------------

def analyze_storage_branches(current_full_or_rel: Optional[str] = None,
                              threshold: float = 0.85) -> Dict[str, Any]:
    """
    storage/ 내 모든 파일의 브랜치 관계 및 패밀리 트리를 분석하여 반환.
    스토리지 서명 기반 0ms 초고속 캐싱 적용.

    Args:
        current_full_or_rel: 현재 열려 있는 파일 경로 (절대 or 상대).
        threshold: 청크 유사도 판단 임계값 (0~1).
    """
    storage_files = get_all_storage_files()

    # 스토리지 서명 생성 (파일경로, mtime, size, 임계값)
    sig_parts = [f"{sf['abs_path']}:{sf['mtime']}:{sf['size']}" for sf in storage_files]
    sig_parts.append(str(threshold))
    storage_sig = hashlib.md5(";".join(sig_parts).encode('utf-8')).hexdigest()

    if _BRANCH_TREE_CACHE["signature"] == storage_sig:
        families = _BRANCH_TREE_CACHE["families"]
        all_tree_nodes = _BRANCH_TREE_CACHE["all_tree_nodes"]
        loaded_files = _BRANCH_TREE_CACHE["loaded_files"]
        categories_list = _BRANCH_TREE_CACHE["categories_list"]
    else:
        loaded_files = []
        for sf in storage_files:
            chunks, first_prompt, sys_inst = get_cached_file_chunks(sf)
            if chunks:
                loaded_files.append({**sf, "chunks": chunks,
                                      "total_chunks": len(chunks),
                                      "first_prompt": first_prompt,
                                      "system_instruction": sys_inst})

        families, all_tree_nodes = _build_families(loaded_files, None, threshold)
        categories_list = _build_categories_list(loaded_files)

        _BRANCH_TREE_CACHE["signature"] = storage_sig
        _BRANCH_TREE_CACHE["families"] = families
        _BRANCH_TREE_CACHE["all_tree_nodes"] = all_tree_nodes
        _BRANCH_TREE_CACHE["loaded_files"] = loaded_files
        _BRANCH_TREE_CACHE["categories_list"] = categories_list

    current_item = _find_current_item(loaded_files, current_full_or_rel)

    active_divergences = _build_active_divergences(current_item, loaded_files, threshold)
    active_lineage = _build_active_lineage(current_item, all_tree_nodes, loaded_files, threshold)

    wv_cfg = load_worldviews_config()
    return {
        "success": True,
        "active_file": current_item["full_path"] if current_item else None,
        "active_total_chunks": len(current_item["chunks"]) if current_item else 0,
        "active_divergences": active_divergences,
        "active_lineage": active_lineage,
        "families": families,
        "categories": categories_list,
        "user_worldviews": wv_cfg.get("worldviews", []),
        "worldview_mappings": wv_cfg.get("mappings", {}),
        "total_files": len(loaded_files),
        "fuzzy_threshold": threshold,
    }


def _find_current_item(loaded_files: List[Dict], current_full_or_rel: Optional[str]
                        ) -> Optional[Dict]:
    """current_full_or_rel에 해당하는 파일 항목을 loaded_files에서 찾아 반환."""
    if not current_full_or_rel:
        return None

    norm_target = normalize_path(current_full_or_rel).lower()
    target_clean = strip_storage_prefix(current_full_or_rel).lower()
    target_basename = os.path.basename(norm_target)

    for lf in loaded_files:
        lf_full = normalize_path(lf.get("full_path", "")).lower()
        lf_rel = normalize_path(lf.get("rel_path", "")).lower()
        lf_name = lf.get("name", "").lower()

        if lf_full == norm_target or lf_rel == target_clean or lf_name == norm_target or lf_name == target_basename:
            return lf
        if lf_rel == norm_target.lstrip("storage/"):
            return lf
    return None


def _build_active_divergences(current_item: Optional[Dict], loaded_files: List[Dict],
                               threshold: float) -> Dict[str, List[Dict]]:
    """현재 파일과 다른 파일들 간의 분기점 정보를 빌드."""
    if not current_item:
        return {}

    curr_chunks = current_item["chunks"]
    curr_total = len(curr_chunks)
    divergences: Dict[str, List[Dict]] = {}

    for other in loaded_files:
        if other["full_path"] == current_item["full_path"]:
            continue

        target_chunks = other["chunks"]
        if not target_chunks or not curr_chunks:
            continue

        # 시작 청크가 불일치하면 브랜치 관계가 성립할 수 없으므로 즉시 스킵
        match, _, _ = are_chunks_similar(curr_chunks[0], target_chunks[0], threshold)
        if not match:
            continue

        lcp = calc_fuzzy_lcp(curr_chunks, target_chunks, threshold)
        if lcp == 0:
            continue

        target_chunks = other["chunks"]
        target_total = len(target_chunks)

        if lcp == curr_total and lcp == target_total:
            rel_type = "identical"
        elif lcp == curr_total:
            rel_type = "target_extends"
        elif lcp == target_total:
            rel_type = "target_ended_here"
        else:
            rel_type = "diverged"

        key = str(lcp - 1)
        divergences.setdefault(key, []).append({
            "name": other["name"],
            "path": other["full_path"],
            "rel_path": other["rel_path"],
            "common_chunks": lcp,
            "fork_chunk_index": lcp - 1,
            "target_total_chunks": target_total,
            "current_total_chunks": curr_total,
            "rel_type": rel_type,
            "target_next_preview": target_chunks[lcp]["preview"] if lcp < target_total else "(대화 종료)",
            "target_next_role": target_chunks[lcp]["role"] if lcp < target_total else "",
            "curr_next_preview": curr_chunks[lcp]["preview"] if lcp < curr_total else "(대화 종료)",
            "curr_next_role": curr_chunks[lcp]["role"] if lcp < curr_total else "",
            "size_formatted": other["size_formatted"],
        })

    return divergences


def _build_families(loaded_files: List[Dict], current_item: Optional[Dict],
                    threshold: float) -> List[Dict]:
    """Union-Find로 관련 파일을 패밀리로 묶고 각 패밀리의 트리를 구성."""
    # Union-Find 초기화
    parent = {lf["full_path"]: lf["full_path"] for lf in loaded_files}

    def find(x: str) -> str:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    n = len(loaded_files)
    lcp_memo: Dict[Tuple[str, str], int] = {}

    def get_lcp(f1: Dict, f2: Dict) -> int:
        p1, p2 = f1["full_path"], f2["full_path"]
        if p1 == p2:
            return f1["total_chunks"]
        key = (p1, p2) if p1 < p2 else (p2, p1)
        if key in lcp_memo:
            return lcp_memo[key]

        # 1번 청크(시작 대화)가 전혀 다르면 LCP는 즉시 0
        c1, c2 = f1["chunks"], f2["chunks"]
        if not c1 or not c2:
            lcp_memo[key] = 0
            return 0

        # 첫 청크 유사도 빠른 판정
        match, _, _ = are_chunks_similar(c1[0], c2[0], threshold)
        if not match:
            lcp_memo[key] = 0
            return 0

        val = calc_fuzzy_lcp(c1, c2, threshold)
        lcp_memo[key] = val
        return val

    for i in range(n):
        for j in range(i + 1, n):
            if get_lcp(loaded_files[i], loaded_files[j]) >= 1:
                union(loaded_files[i]["full_path"], loaded_files[j]["full_path"])

    # 패밀리 그룹화
    family_groups: Dict[str, List[Dict]] = {}
    for lf in loaded_files:
        family_groups.setdefault(find(lf["full_path"]), []).append(lf)

    families = []
    all_tree_nodes: Dict[str, Dict] = {}
    for fam_idx, (_root_key, members) in enumerate(family_groups.items(), start=1):
        # 청크 수가 가장 적은 파일이 Trunk Root
        members.sort(key=lambda x: (x["total_chunks"], x["name"]))
        root_trunk = members[0]

        tree_node_map = {
            m["full_path"]: _make_tree_node(m, current_item, m == root_trunk)
            for m in members
        }

        # 부모-자식 관계 결정 (조상 계통 및 청크 일치도 기반)
        for i in range(1, len(members)):
            m = members[i]
            m_chunks = m["chunks"]
            m_len = len(m_chunks)

            best_parent = root_trunk
            best_score = -1
            best_common = get_lcp(m, root_trunk)

            for j, cand in enumerate(members):
                if i == j or cand["total_chunks"] >= m["total_chunks"]:
                    continue

                c_chunks = cand["chunks"]
                c_len = len(c_chunks)
                if c_len == 0:
                    continue

                lcp = get_lcp(m, cand)
                if lcp == 0:
                    continue

                # 조상 파일의 청크 구간(0 ~ c_len - 1) 중 일치하는 청크 수 계산
                matched_count = 0
                for c_i in range(min(c_len, m_len)):
                    match, _, _ = are_chunks_similar(c_chunks[c_i], m_chunks[c_i], threshold)
                    if match:
                        matched_count += 1

                match_ratio = matched_count / c_len if c_len > 0 else 0.0

                if match_ratio >= 0.7:
                    # 부모 청크의 70% 이상 일치: 직전 조상 체인으로 인정 (일부 청크 수정 허용)
                    perfect_bonus = 200 if lcp == c_len else 0
                    score = matched_count * 1000 + c_len * 10 + perfect_bonus
                    common = c_len
                else:
                    # 분기된 다른 가지이거나 일부만 공유
                    score = lcp * 100 + matched_count
                    common = lcp

                if score > best_score:
                    best_score = score
                    best_parent = cand
                    best_common = common

            node = tree_node_map[m["full_path"]]
            node.update({
                "parent_name": best_parent["name"],
                "parent_path": best_parent["full_path"],
                "fork_at_chunk": best_common - 1 if best_common > 0 else 0,
                "fork_turn": best_common,
                "common_with_parent": best_common,
            })
            tree_node_map[best_parent["full_path"]]["children"].append(node)

        all_tree_nodes.update(tree_node_map)
        root_tree = tree_node_map[root_trunk["full_path"]]
        flat_tree_list = _flatten_tree(root_tree)

        families.append({
            "id": f"fam_{fam_idx}",
            "title": root_trunk["name"],
            "category": root_trunk.get("category", "미분류"),
            "folder": root_trunk.get("folder", ""),
            "root_prompt": root_trunk["first_prompt"] or root_trunk["name"],
            "root_total_chunks": root_trunk["total_chunks"],
            "files_count": len(members),
            "tree": root_tree,
            "files": flat_tree_list,
        })

    return families, all_tree_nodes


def _extract_direct_children(node: Dict) -> List[Dict]:
    """트리 노드의 직속 자식 목록을 추출하여 반환."""
    children = []
    for ch in node.get("children", []):
        children.append({
            "name": ch["name"],
            "rel_path": ch["rel_path"],
            "full_path": ch["full_path"],
            "category": ch.get("category", "미분류"),
            "total_chunks": ch.get("total_chunks", 0),
            "common_with_parent": ch.get("common_with_parent", 0),
            "fork_at_chunk": ch.get("fork_at_chunk", 0),
            "size_formatted": ch.get("size_formatted", ""),
            "first_prompt": ch.get("first_prompt", ""),
        })
    return children


def _extract_all_descendants(node: Dict, all_tree_nodes: Dict[str, Dict]) -> List[Dict]:
    """트리 노드의 모든 하위 자손(직속 자식 및 그 하위 자식들 전체)을 추출하여 반환."""
    descendants = []
    stack = list(node.get("children", []))
    visited = set()
    while stack:
        curr = stack.pop()
        fp = curr.get("full_path")
        if fp and fp not in visited:
            visited.add(fp)
            tree_node = all_tree_nodes.get(fp, curr)
            descendants.append({
                "name": curr["name"],
                "rel_path": curr["rel_path"],
                "full_path": curr["full_path"],
                "category": curr.get("category", "미분류"),
                "total_chunks": curr.get("total_chunks", 0),
                "parent_name": curr.get("parent_name", ""),
                "common_with_parent": curr.get("common_with_parent", 0),
            })
            for child in tree_node.get("children", []):
                if child.get("full_path") not in visited:
                    stack.append(child)
    return descendants


def _build_active_lineage(current_item: Optional[Dict],
                          all_tree_nodes: Dict[str, Dict],
                          loaded_files: List[Dict],
                          threshold: float = 0.85) -> Dict[str, Any]:
    """
    현재 활성 파일의 심층 조상 체인(Root -> Intermediate -> Direct Parent) 및
    각 조상별 상속 청크 인덱스 범위, 수정 여부, 직속 자식 및 하위 자손 목록을 분석하여 반환.
    """
    if not current_item or current_item["full_path"] not in all_tree_nodes:
        return {
            "has_parent": False,
            "inherited_total_chunks": 0,
            "own_start_chunk_index": 0,
            "own_chunks_count": current_item["total_chunks"] if current_item else 0,
            "ancestors": [],
            "direct_children": [],
            "all_descendants": [],
            "all_descendants_count": 0,
            "chain_summary": "최상위 단독 파일",
        }

    curr_path = current_item["full_path"]
    curr_node = all_tree_nodes[curr_path]
    curr_chunks = current_item["chunks"]
    curr_total = len(curr_chunks)
    loaded_files_map = {lf["full_path"]: lf for lf in loaded_files}

    # 1. 조상 체인 거슬러 올라가기 (Bottom-Up: 현재 -> 부모 -> 부모의 부모 -> ... -> 루트)
    raw_ancestors: List[Tuple[Dict, int]] = []
    visited = set()
    node_ptr = curr_node
    while node_ptr.get("parent_path") and node_ptr["parent_path"] not in visited:
        p_path = node_ptr["parent_path"]
        visited.add(p_path)
        if p_path not in all_tree_nodes:
            break
        p_node = all_tree_nodes[p_path]
        common = node_ptr.get("common_with_parent", 0)
        raw_ancestors.append((p_node, common))
        node_ptr = p_node

    direct_children = _extract_direct_children(curr_node)
    all_descendants = _extract_all_descendants(curr_node, all_tree_nodes)

    if not raw_ancestors:
        # 루트 노드 (상속받은 부모가 없음)
        return {
            "has_parent": False,
            "inherited_total_chunks": 0,
            "own_start_chunk_index": 0,
            "own_chunks_count": curr_total,
            "ancestors": [],
            "direct_children": direct_children,
            "all_descendants": all_descendants,
            "all_descendants_count": len(all_descendants),
            "chain_summary": f"{current_item['name']} (최상위 루트 세션, 총 {curr_total}개 청크)",
        }

    # raw_ancestors: [직전 부모, ..., 루트] -> [루트, ..., 직전 부모]
    raw_ancestors.reverse()

    # 2. 각 조상별 상속 청크 범위(Chunk Ranges) 계산
    ancestors_info = []
    prev_chunk_end = 0
    direct_parent_common = curr_node.get("common_with_parent", 0)

    for idx, (anc_node, common_with_child) in enumerate(raw_ancestors):
        anc_path = anc_node["full_path"]
        anc_file = loaded_files_map.get(anc_path)
        anc_chunks = anc_file["chunks"] if anc_file else []

        is_direct_parent = (idx == len(raw_ancestors) - 1)
        is_root = (idx == 0)

        if is_direct_parent:
            chunk_end = direct_parent_common - 1
        else:
            next_common = raw_ancestors[idx + 1][1]
            chunk_end = min(next_common, anc_node["total_chunks"]) - 1

        chunk_start = prev_chunk_end
        chunk_count = max(0, chunk_end - chunk_start + 1)

        # 3. 조상 파일이 디스크 상에서 수정되었는지(is_modified) 정밀 감지
        is_modified = False
        diverged_chunk_idx = None
        if anc_chunks and chunk_count > 0:
            for c_i in range(chunk_start, min(chunk_end + 1, len(curr_chunks), len(anc_chunks))):
                match, ratio, _ = are_chunks_similar(curr_chunks[c_i], anc_chunks[c_i], threshold)
                if not match:
                    is_modified = True
                    diverged_chunk_idx = c_i
                    break

        ancestors_info.append({
            "depth": idx,
            "name": anc_node["name"],
            "rel_path": anc_node["rel_path"],
            "full_path": anc_node["full_path"],
            "category": anc_node.get("category", "미분류"),
            "total_chunks": anc_node["total_chunks"],
            "chunk_range_start": chunk_start,
            "chunk_range_end": chunk_end,
            "chunk_count": chunk_count,
            "chunk_range_display": f"#{chunk_start + 1} ~ #{chunk_end + 1}" if chunk_count > 0 else "-",
            "is_direct_parent": is_direct_parent,
            "is_root": is_root,
            "is_modified_in_parent": is_modified,
            "diverged_at_chunk": diverged_chunk_idx,
            "diverged_chunk_display": f"#{diverged_chunk_idx + 1}" if diverged_chunk_idx is not None else None,
        })

        prev_chunk_end = chunk_end + 1

    inherited_total = direct_parent_common
    own_start = direct_parent_common
    own_count = max(0, curr_total - inherited_total)

    chain_parts = [f"{a['name']} ({a['chunk_range_display']})" for a in ancestors_info]
    chain_parts.append(f"{current_item['name']} [고유 #{own_start + 1}~#{curr_total}]")
    chain_summary = " -> ".join(chain_parts)

    return {
        "has_parent": True,
        "inherited_total_chunks": inherited_total,
        "own_start_chunk_index": own_start,
        "own_chunks_count": own_count,
        "ancestors": ancestors_info,
        "direct_children": direct_children,
        "all_descendants": all_descendants,
        "all_descendants_count": len(all_descendants),
        "chain_summary": chain_summary,
    }


def _make_tree_node(m: Dict, current_item: Optional[Dict], is_root: bool) -> Dict:
    """파일 정보로 트리 노드 딕셔너리를 생성."""
    return {
        "id": m["full_path"],
        "name": m["name"],
        "rel_path": m["rel_path"],
        "category": m.get("category", "미분류"),
        "folder": m.get("folder", ""),
        "full_path": m["full_path"],
        "total_chunks": m["total_chunks"],
        "size_formatted": m["size_formatted"],
        "mtime": m["mtime"],
        "is_active": (current_item is not None and m["full_path"] == current_item["full_path"]),
        "is_root": is_root,
        "parent_name": None,
        "parent_path": None,
        "fork_at_chunk": None,
        "fork_turn": 0,
        "common_with_parent": 0,
        "depth": 0,
        "first_prompt": m["first_prompt"],
        "children": [],
    }


def _flatten_tree(node: Dict, depth: int = 0) -> List[Dict]:
    """트리를 pre-order 순회하여 depth를 채운 평탄 리스트로 반환."""
    node["depth"] = depth
    result = [node]
    for child in node["children"]:
        result.extend(_flatten_tree(child, depth + 1))
    return result


def _build_categories_list(loaded_files: List[Dict]) -> List[Dict]:
    """파일 목록에서 카테고리별 파일 수를 집계하여 반환."""
    cat_counts: Dict[str, int] = {}
    for lf in loaded_files:
        cat = lf.get("category", "미분류")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    wv_cfg = load_worldviews_config()
    seen: set = set()
    categories = []
    for wv in wv_cfg.get("worldviews", []):
        categories.append({"name": wv, "count": cat_counts.get(wv, 0), "is_custom": True})
        seen.add(wv)
    for cat, count in cat_counts.items():
        if cat not in seen:
            categories.append({"name": cat, "count": count, "is_custom": False})
            seen.add(cat)
    return categories


# ---------------------------------------------------------------------------
# 보관함 전체 및 세계관 고속 검색
# ---------------------------------------------------------------------------

def search_in_storage(query: str, scope: str = "all", target_worldview: Optional[str] = None,
                      target_file: Optional[str] = None, max_results: int = 150) -> Dict[str, Any]:
    """
    보관함 내 대화 파일들의 청크 본문을 고속 검색.
    - query: 검색어
    - scope: 'current' (단일 파일), 'worldview' (지정 세계관), 'all' (전체)
    - target_worldview: scope가 'worldview'일 때 필터링할 세계관 이름
    - target_file: scope가 'current'일 때 대상 파일의 상대 경로 또는 파일명
    """
    clean_query = query.strip()
    if not clean_query:
        return {"query": "", "scope": scope, "results": [], "total_matches": 0, "files_searched": 0}

    q_lower = clean_query.lower()
    wv_cfg = load_worldviews_config()
    norm_mappings = _build_normalized_mappings(wv_cfg.get("mappings", {}))

    results = []
    files_searched = 0

    target_file_norm = normalize_path(target_file).lstrip("storage/").lstrip("/") if target_file else None

    # STORAGE_DIR 및 BASE_DIR 루트 파일 검색
    search_dirs = [STORAGE_DIR]

    for s_dir in search_dirs:
        for root, _dirs, files in os.walk(s_dir):
            for filename in files:
                abs_path = normalize_path(os.path.abspath(os.path.join(root, filename)))
                if not is_valid_json_file(abs_path, filename):
                    continue

                rel_path = normalize_path(os.path.relpath(abs_path, STORAGE_DIR))
                clean_rel = rel_path.lstrip("storage/").lstrip("/")
                rel_parts = rel_path.split("/")
                category = _resolve_category(rel_path, filename, rel_parts, norm_mappings)

                # scope 조건 확인
                if scope == "current" and target_file_norm:
                    if clean_rel.lower() != target_file_norm.lower() and filename.lower() != target_file_norm.lower():
                        continue
                elif scope == "worldview" and target_worldview:
                    if category != target_worldview:
                        continue

                files_searched += 1

                # 1단계: 초고속 텍스트 선별 (raw text contains 검사)
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_content = f.read()
                except Exception:
                    continue

                if q_lower not in raw_content.lower():
                    continue

                # 2단계: 일치하는 파일만 청크 파싱
                try:
                    data = json.loads(raw_content)
                except Exception:
                    continue

                chunks = data.get("chunkedPrompt", {}).get("chunks", [])
                if not isinstance(chunks, list):
                    continue

                for c_idx, chunk in enumerate(chunks):
                    if not isinstance(chunk, dict):
                        continue
                    is_thought = bool(chunk.get("isThought", False))
                    text, is_thought = _extract_chunk_text(chunk, is_thought)
                    if not text:
                        continue

                    text_lower = text.lower()
                    pos = text_lower.find(q_lower)
                    if pos != -1:
                        start = max(0, pos - 40)
                        end = min(len(text), pos + len(clean_query) + 40)
                        snippet = ("..." if start > 0 else "") + text[start:end].replace("\r", " ").replace("\n", " ") + ("..." if end < len(text) else "")

                        results.append({
                            "filename": filename,
                            "rel_path": rel_path,
                            "category": category,
                            "chunk_index": c_idx,
                            "role": "thought" if is_thought else chunk.get("role", "user"),
                            "snippet": snippet,
                        })

                        if len(results) >= max_results:
                            break

                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

    return {
        "query": clean_query,
        "scope": scope,
        "worldview": target_worldview,
        "results": results,
        "total_matches": len(results),
        "files_searched": files_searched,
        "truncated": len(results) >= max_results
    }


# ---------------------------------------------------------------------------
# 파일 경로 해석 헬퍼
# ---------------------------------------------------------------------------

def resolve_file_path(filename: str) -> Optional[str]:
    """
    다양한 형태의 파일 경로 문자열을 실제 절대 경로로 해석.

    우선순위:
      1. 절대 경로
      2. BASE_DIR 기준 상대 경로
      3. STORAGE_DIR 기준 상대 경로
      4. 'storage/' 접두어 제거 후 STORAGE_DIR 기준
      5. 파일명(basename)으로 STORAGE_DIR 내 전체 탐색
    """
    filename = filename.strip()

    # 1. 절대 경로
    if os.path.isabs(filename):
        abs_target = os.path.abspath(filename)
        if os.path.exists(abs_target) and is_safe_path(BASE_DIR, abs_target):
            return abs_target

    # 2. BASE_DIR 기준
    candidate = os.path.abspath(os.path.join(BASE_DIR, filename))
    if os.path.exists(candidate) and is_safe_path(BASE_DIR, candidate):
        return candidate

    # 3. STORAGE_DIR 기준
    candidate = os.path.abspath(os.path.join(STORAGE_DIR, filename))
    if os.path.exists(candidate) and is_safe_path(STORAGE_DIR, candidate):
        return candidate

    # 4. 'storage/' 접두어 제거
    clean = strip_storage_prefix(filename)
    if clean != filename:
        candidate = os.path.abspath(os.path.join(STORAGE_DIR, clean))
        if os.path.exists(candidate) and is_safe_path(STORAGE_DIR, candidate):
            return candidate

    # 5. basename으로 STORAGE_DIR 전체 탐색
    raw_base = os.path.basename(normalize_path(filename).split("\t")[-1])
    for root, _dirs, files in os.walk(STORAGE_DIR):
        if raw_base in files:
            cand = os.path.abspath(os.path.join(root, raw_base))
            if is_safe_path(STORAGE_DIR, cand):
                return cand

    # 5b. 저장 파일 목록 대조
    for sf in get_all_storage_files():
        if sf["rel_path"] == clean or sf["name"] == clean or sf["full_path"] == filename:
            return sf["full_path"]

    return None


# ---------------------------------------------------------------------------
# HTTP 요청 핸들러
# ---------------------------------------------------------------------------

def _path_eq(actual: str, expected: str) -> bool:
    """후행 슬래시를 무시한 경로 비교."""
    return actual.rstrip("/") == expected.rstrip("/")


class AISHandler(http.server.SimpleHTTPRequestHandler):
    """Google AI Studio JSON Manager 전용 HTTP 요청 핸들러."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    # ------------------------------------------------------------------
    # GET 라우팅
    # ------------------------------------------------------------------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        routes = {
            "/api/status":           self._get_status,
            "/api/list":             self._get_list,
            "/api/storage/tree":     self._get_storage_tree,
            "/api/worldviews":       self._get_worldviews,
            "/api/storage/branches": lambda: self._get_storage_branches(qs),
            "/api/storage/diff_analysis": lambda: self._get_diff_analysis(qs),
            "/api/fonts":            self._get_fonts,
            "/api/file":             lambda: self._get_file(qs),
            "/api/search":           lambda: self._get_search(qs),
            "/api/settings":         self._get_settings,
            "/api/open-manual":      self._get_open_manual,
        }

        for route, handler in routes.items():
            if _path_eq(path, route):
                handler()
                return

        super().do_GET()  # 정적 파일 서빙

    def _get_settings(self):
        self._send_json(load_app_settings())

    def _get_open_manual(self):
        """기능 종합 설명서(manual.html)를 시스템 기본 웹 브라우저로 엽니다."""
        import webbrowser
        try:
            port = self.server.server_address[1]
            webbrowser.open(f"http://127.0.0.1:{port}/manual.html")
            self._send_json({"ok": True})
        except Exception as e:
            self._send_error(500, f"설명서 열기 실패: {e}")

    def _get_search(self, qs):
        query = (qs.get("q", [""])[0]).strip()
        scope = (qs.get("scope", ["all"])[0]).strip()
        worldview = (qs.get("worldview", [""])[0]).strip() or None
        target_file = (qs.get("file", [""])[0]).strip() or None
        res = search_in_storage(query=query, scope=scope, target_worldview=worldview, target_file=target_file)
        self._send_json(res)

    def _get_status(self):
        self._send_json({"status": "ok", "mode": "local_server", "cwd": BASE_DIR})

    def _get_list(self):
        files = [
            f for f in os.listdir(BASE_DIR)
            if is_valid_json_file(os.path.join(BASE_DIR, f), f)
        ]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(BASE_DIR, x)), reverse=True)
        self._send_json(files)

    def _get_storage_tree(self):
        self._send_json({
            "tree": get_storage_tree(STORAGE_DIR),
            "root_files": get_root_json_files(),
        })

    def _get_worldviews(self):
        self._send_json(load_worldviews_config())

    def _get_storage_branches(self, qs: Dict):
        current_path = qs.get("current", [None])[0]
        threshold = self._parse_float(qs.get("threshold", ["0.85"])[0], 0.85)
        try:
            self._send_json(analyze_storage_branches(current_path, threshold=threshold))
        except Exception as e:
            self._send_error(500, f"Error analyzing branches: {e}")

    def _get_diff_analysis(self, qs: Dict):
        file_a_path = qs.get("fileA", [None])[0]
        file_b_path = qs.get("fileB", [None])[0]
        if not file_a_path or not file_b_path:
            self._send_error(400, "Missing fileA or fileB query parameter")
            return

        fp_a = resolve_file_path(file_a_path)
        fp_b = resolve_file_path(file_b_path)
        if not fp_a or not fp_b:
            self._send_error(404, "One or both files not found")
            return

        threshold = self._parse_float(qs.get("threshold", ["0.85"])[0], 0.85)
        try:
            result = self._compute_diff(fp_a, fp_b, threshold)
            self._send_json(result)
        except Exception as e:
            self._send_error(500, f"Error diffing files: {e}")

    def _compute_diff(self, fp_a: str, fp_b: str, threshold: float) -> Dict:
        """두 파일의 청크를 비교하여 상세 diff 결과를 반환."""
        with open(fp_a, "r", encoding="utf-8") as f:
            data_a = json.load(f)
        with open(fp_b, "r", encoding="utf-8") as f:
            data_b = json.load(f)

        chunks_a = extract_chunks_signature(data_a)
        chunks_b = extract_chunks_signature(data_b)
        max_len = max(len(chunks_a), len(chunks_b))

        comparisons = []
        lcp = 0
        still_matching = True
        identical_count = 0
        fuzzy_count = 0

        for idx in range(max_len):
            cA = chunks_a[idx] if idx < len(chunks_a) else None
            cB = chunks_b[idx] if idx < len(chunks_b) else None

            if cA is not None and cB is not None:
                is_match, ratio, match_type = are_chunks_similar(cA, cB, threshold)
                sim_pct = round(ratio * 100, 1)
                if match_type in ("exact", "whitespace_only"):
                    identical_count += 1
                elif match_type == "fuzzy":
                    fuzzy_count += 1
                if is_match and still_matching:
                    lcp += 1
                else:
                    still_matching = False

                comparisons.append({
                    "chunk_index": idx + 1,
                    "role_a": cA["role"], "role_b": cB["role"],
                    "similarity_pct": sim_pct, "match_type": match_type,
                    "is_match": is_match,
                    "len_a": cA["length"], "len_b": cB["length"],
                    "preview_a": cA["preview"], "preview_b": cB["preview"],
                    "text_a": (cA.get("sample") or cA.get("text") or "")[:4000],
                    "text_b": (cB.get("sample") or cB.get("text") or "")[:4000],
                })
            else:
                still_matching = False
                comparisons.append({
                    "chunk_index": idx + 1,
                    "role_a": cA["role"] if cA else None,
                    "role_b": cB["role"] if cB else None,
                    "similarity_pct": 0.0, "match_type": "ended_in_one",
                    "is_match": False,
                    "len_a": cA["length"] if cA else 0,
                    "len_b": cB["length"] if cB else 0,
                    "preview_a": cA["preview"] if cA else "(이 파일은 대화 종료)",
                    "preview_b": cB["preview"] if cB else "(이 파일은 대화 종료)",
                    "text_a": ((cA.get("sample") or cA.get("text") or "") if cA else "")[:4000],
                    "text_b": ((cB.get("sample") or cB.get("text") or "") if cB else "")[:4000],
                })

        return {
            "success": True,
            "file_a": os.path.basename(fp_a),
            "file_b": os.path.basename(fp_b),
            "total_chunks_a": len(chunks_a),
            "total_chunks_b": len(chunks_b),
            "lcp": lcp,
            "first_divergence_turn": lcp + 1 if lcp < max_len else None,
            "identical_count": identical_count,
            "fuzzy_count": fuzzy_count,
            "threshold_used": threshold,
            "comparisons": comparisons,
        }

    def _get_fonts(self):
        fonts_dir = os.path.join(BASE_DIR, "fonts")
        font_list = []
        if os.path.exists(fonts_dir):
            for filename in os.listdir(fonts_dir):
                ext = os.path.splitext(filename)[1].lower()
                if ext in FONT_EXTENSIONS:
                    font_list.append({
                        "name": os.path.splitext(filename)[0],
                        "filename": filename,
                        "format": FONT_EXTENSIONS[ext],
                        "url": f"/fonts/{urllib.parse.quote(filename)}",
                    })
        self._send_json(font_list)

    def _get_file(self, qs: Dict):
        filename = (qs.get("path", [None])[0] or qs.get("name", [None])[0])
        if not filename:
            self._send_error(400, "Missing filename")
            return

        filepath = resolve_file_path(filename)
        if not filepath or not os.path.isfile(filepath):
            self._send_error(404, f"File not found: {filename}")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self._send_json(json.load(f))
        except Exception as e:
            self._send_error(500, f"Error reading file: {e}")

    # ------------------------------------------------------------------
    # POST 라우팅
    # ------------------------------------------------------------------

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        post_routes = {
            "/api/worldviews":          self._post_worldviews,
            "/api/save":                self._post_save,
            "/api/storage/mkdir":       self._post_mkdir,
            "/api/storage/move":        self._post_move,
            "/api/storage/rename":      self._post_rename,
            "/api/storage/delete":      self._post_delete,
            "/api/storage/upload":      self._post_upload,
            "/api/storage/branch_off":  self._post_branch_off,
            "/api/rename":              self._post_rename_root,
            "/api/upload_font":         self._post_upload_font,
            "/api/settings":            self._post_settings,
            "/api/clipboard":           self._post_clipboard,
            "/api/storage/sync-lineage":      self._post_sync_lineage,
            "/api/storage/propagate-lineage": self._post_propagate_lineage,
            "/api/storage/open-external":     self._post_open_external,
            "/api/download-to-c":             self._post_download_to_c,
        }

        for route, handler in post_routes.items():
            if _path_eq(path, route):
                handler()
                return

        self._send_error(404, "Endpoint not found")

    # ---------- POST 핸들러 ----------

    def _post_sync_lineage(self):
        """
        심층 계통도에서 특정 조상 파일의 해당 청크 구간(chunk_range_start ~ chunk_range_end)만
        현재 자식 파일에 안전하게 1클릭 동기화(치환).
        다른 구간(윗대 조상 구간, 현재 파일 고유 대화 등)은 100% 보존됨.
        """
        payload = self._read_json_body()
        if payload is None:
            return

        target_file = payload.get("target_file")
        ancestor_file = payload.get("ancestor_file")
        start_idx = payload.get("chunk_range_start")
        end_idx = payload.get("chunk_range_end")

        if not target_file or not ancestor_file or start_idx is None or end_idx is None:
            self._send_error(400, "Missing required parameters (target_file, ancestor_file, chunk_range_start, chunk_range_end)")
            return

        try:
            start_idx = int(start_idx)
            end_idx = int(end_idx)
            if start_idx < 0:
                self._send_error(400, f"Invalid start_idx: {start_idx}")
                return
        except ValueError:
            self._send_error(400, "chunk_range_start and chunk_range_end must be integers")
            return

        target_path = resolve_file_path(target_file)
        ancestor_path = resolve_file_path(ancestor_file)

        if not target_path or not os.path.exists(target_path):
            self._send_error(404, f"Target file not found: {target_file}")
            return
        if not ancestor_path or not os.path.exists(ancestor_path):
            self._send_error(404, f"Ancestor file not found: {ancestor_file}")
            return

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                target_data = json.load(f)
            with open(ancestor_path, "r", encoding="utf-8") as f:
                ancestor_data = json.load(f)

            target_chunks = target_data.get("chunkedPrompt", {}).get("chunks", [])
            ancestor_chunks = ancestor_data.get("chunkedPrompt", {}).get("chunks", [])

            if not isinstance(target_chunks, list) or not isinstance(ancestor_chunks, list):
                self._send_error(400, "Invalid JSON structure (missing chunkedPrompt.chunks)")
                return

            if len(ancestor_chunks) == 0:
                self._send_error(400, "Ancestor file has no chunks")
                return

            # 조상 파일 크기에 맞춰 end_idx 자동 보정
            if end_idx >= len(ancestor_chunks):
                end_idx = len(ancestor_chunks) - 1

            if start_idx > end_idx:
                start_idx = 0

            # 안전 백업 생성
            backup_path = target_path + ".bak_lineage"
            try:
                shutil.copy2(target_path, backup_path)
            except Exception as b_err:
                print(f"[Lineage Sync] 백업 생성 경고: {b_err}")

            # 조상 파일에서 해당 구간 청크 복사
            fresh_ancestor_chunks = copy.deepcopy(ancestor_chunks[start_idx:end_idx + 1])

            # 대상 파일의 해당 구간 치환
            # 만약 0번부터 시작하는 상속 구간 전체 치환인 경우, 자식의 고유 대화 보존을 위해 슬라이스 교체
            target_chunks[start_idx:end_idx + 1] = fresh_ancestor_chunks
            target_data["chunkedPrompt"]["chunks"] = target_chunks

            # 저장
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(target_data, f, ensure_ascii=False, indent=2)

            # 캐시 무효화
            if target_path in _FILE_CHUNKS_CACHE:
                del _FILE_CHUNKS_CACHE[target_path]
            invalidate_branch_tree_cache()

            sync_count = len(fresh_ancestor_chunks)
            print(f"[Lineage Sync] 동기화 성공: '{os.path.basename(target_path)}' #{start_idx+1}~#{end_idx+1} ({sync_count}개 청크) from '{os.path.basename(ancestor_path)}'")

            self._send_json({
                "success": True,
                "message": f"'{os.path.basename(ancestor_path)}'의 최신 내용으로 #{start_idx+1}~#{end_idx+1} ({sync_count}개 청크) 구간을 연동했습니다.",
                "synced_count": sync_count,
                "chunk_range_start": start_idx,
                "chunk_range_end": end_idx,
                "updated_data": target_data,
                "backup_file": os.path.basename(backup_path),
            })
        except Exception as e:
            print(f"[Lineage Sync Error] {e}\n{traceback.format_exc()}")
            self._send_error(500, f"Error syncing lineage chunk range: {e}")

    def _post_propagate_lineage(self):
        """
        부모 세션 파일의 변경사항을 이 부모를 상속받은 모든 하위 자식 세션 파일들에
        일괄로 연동(해당 부모 청크 구간 교체)합니다.
        자식 세션들의 고유 대화(부모 이후의 대화)는 100% 안전하게 유지됩니다.
        """
        payload = self._read_json_body()
        if payload is None:
            return

        parent_file = payload.get("parent_file")
        client_parent_chunks = payload.get("parent_chunks")  # 클라이언트가 보낸 최신 청크 (옵션)

        if not parent_file:
            self._send_error(400, "Missing parent_file parameter")
            return

        parent_path = resolve_file_path(parent_file)
        if not parent_path or not os.path.exists(parent_path):
            self._send_error(404, f"Parent file not found: {parent_file}")
            return

        try:
            # 부모 파일 읽기
            with open(parent_path, "r", encoding="utf-8") as f:
                parent_data = json.load(f)

            # 클라이언트에서 최신 청크 목록을 보냈다면 부모 파일에 먼저 반영 & 저장
            if isinstance(client_parent_chunks, list) and len(client_parent_chunks) > 0:
                parent_chunks = client_parent_chunks
                parent_data.setdefault("chunkedPrompt", {})["chunks"] = parent_chunks
                with open(parent_path, "w", encoding="utf-8") as f:
                    json.dump(parent_data, f, ensure_ascii=False, indent=2)
            else:
                parent_chunks = parent_data.get("chunkedPrompt", {}).get("chunks", [])

            parent_total = len(parent_chunks)
            if parent_total == 0:
                self._send_error(400, "Parent file has no chunks to propagate")
                return

            parent_sig_chunks = extract_chunks_signature({"chunkedPrompt": {"chunks": parent_chunks}})

            # 청크 캐시 무효화 후 브랜치 트리 분석으로 자손 탐색
            if parent_path in _FILE_CHUNKS_CACHE:
                del _FILE_CHUNKS_CACHE[parent_path]
            invalidate_branch_tree_cache()

            branch_info = analyze_storage_branches(parent_path)
            lineage = branch_info.get("active_lineage", {})
            descendants = lineage.get("all_descendants", [])

            # 자손 목록이 트리에서 비어 있는 경우를 대비해 스토리지 파일 직접 검사
            found_paths = {d.get("full_path") for d in descendants if d.get("full_path")}
            all_storage = get_all_storage_files()

            for sf in all_storage:
                sf_path = sf["abs_path"]
                if sf_path == normalize_path(parent_path) or sf_path in found_paths:
                    continue
                c_chunks, _, _ = get_cached_file_chunks(sf)
                if not c_chunks or len(c_chunks) < parent_total:
                    continue
                # 첫 청크 유사 판정
                match, _, _ = are_chunks_similar(c_chunks[0], parent_sig_chunks[0], 0.8)
                if not match:
                    continue
                # 상속 청크 수 계산
                lcp = calc_fuzzy_lcp(c_chunks, parent_sig_chunks, 0.8)
                if lcp >= max(2, int(parent_total * 0.6)):
                    descendants.append({
                        "name": sf["name"],
                        "rel_path": sf["rel_path"],
                        "full_path": sf_path,
                        "common_with_parent": lcp,
                    })
                    found_paths.add(sf_path)

            if not descendants:
                self._send_json({
                    "success": True,
                    "synced_count": 0,
                    "synced_files": [],
                    "message": "이 부모 세션을 공유하는 하위 자식 세션이 없습니다."
                })
                return

            synced_results = []
            for desc in descendants:
                c_path = desc.get("full_path")
                if not c_path or not os.path.exists(c_path):
                    continue

                try:
                    with open(c_path, "r", encoding="utf-8") as cf:
                        child_data = json.load(cf)

                    child_chunks = child_data.get("chunkedPrompt", {}).get("chunks", [])
                    if not isinstance(child_chunks, list):
                        continue

                    # 자식이 원래 부모로부터 상속받고 있던 청크 개수 파악
                    orig_common = desc.get("common_with_parent", parent_total)
                    if orig_common > len(child_chunks):
                        orig_common = min(parent_total, len(child_chunks))

                    # 자식의 고유 대화(#orig_common 이후 청크들) 분리
                    child_own_chunks = child_chunks[orig_common:]

                    # 백업 생성
                    bak_path = c_path + ".bak_lineage"
                    try:
                        shutil.copy2(c_path, bak_path)
                    except Exception:
                        pass

                    # 부모의 최신 청크 전체 + 자식의 고유 대화로 안전 조립!
                    fresh_parent_chunks = copy.deepcopy(parent_chunks)
                    new_child_chunks = fresh_parent_chunks + child_own_chunks
                    child_data["chunkedPrompt"]["chunks"] = new_child_chunks

                    with open(c_path, "w", encoding="utf-8") as cf:
                        json.dump(child_data, cf, ensure_ascii=False, indent=2)

                    if c_path in _FILE_CHUNKS_CACHE:
                        del _FILE_CHUNKS_CACHE[c_path]

                    synced_results.append({
                        "name": desc.get("name"),
                        "rel_path": desc.get("rel_path"),
                        "chunks_synced": parent_total,
                        "child_total": len(new_child_chunks),
                    })
                except Exception as c_err:
                    print(f"[Lineage Propagate] Error updating child {c_path}: {c_err}")

            if parent_path in _FILE_CHUNKS_CACHE:
                del _FILE_CHUNKS_CACHE[parent_path]
            invalidate_branch_tree_cache()

            self._send_json({
                "success": True,
                "synced_count": len(synced_results),
                "synced_files": synced_results,
                "message": f"하위 {len(synced_results)}개 세션 파일의 공통 대화 구간(총 {parent_total}개 청크)이 최신 내용으로 모두 일괄 연동되었습니다!"
            })
        except Exception as e:
            print(f"[Lineage Propagate Error] {e}\n{traceback.format_exc()}")
            self._send_error(500, f"Error propagating lineage: {e}")

    def _post_open_external(self):
        """
        Windows 시스템 앱(메모장 또는 탐색기)으로 해당 JSON 파일/폴더를 즉시 엽니다.
        """
        payload = self._read_json_body()
        if payload is None:
            return

        file_path = payload.get("file_path")
        action = payload.get("action", "notepad")

        if not file_path:
            self._send_error(400, "Missing file_path parameter")
            return

        abs_path = resolve_file_path(file_path)
        if not abs_path or not os.path.exists(abs_path):
            self._send_error(404, f"File not found: {file_path}")
            return

        norm_path = os.path.normpath(abs_path)
        try:
            if action == "notepad":
                # 메모장으로 파일 직접 실행
                subprocess.Popen(["notepad.exe", norm_path])
                self._send_json({"success": True, "message": f"'{os.path.basename(norm_path)}'을(를) 메모장으로 열었습니다."})
            elif action == "explorer":
                # Windows 탐색기에서 해당 파일을 포커스하여 폴더 열기
                subprocess.Popen(f'explorer.exe /select,"{norm_path}"')
                self._send_json({"success": True, "message": f"'{os.path.basename(norm_path)}'의 위치를 탐색기에서 열었습니다."})
            else:
                self._send_error(400, f"Unsupported action: {action}")
        except Exception as e:
            print(f"[Open External Error] {e}\n{traceback.format_exc()}")
            self._send_error(500, f"Failed to open external app: {e}")

    def _post_download_to_c(self):
        """
        현재 작업 중인 대화 JSON 내용을 C 드라이브 사용자 Downloads 폴더에 즉시 저장합니다.
        """
        payload = self._read_json_body()
        if payload is None:
            return
        raw_name = (payload.get("filename") or "ai_studio_export.json").strip()
        safe_name = os.path.basename(raw_name)
        if not safe_name.lower().endswith(".json"):
            safe_name += ".json"
        content = payload.get("content")

        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(downloads_dir, exist_ok=True)
            target_path = os.path.join(downloads_dir, safe_name)
            with open(target_path, "w", encoding="utf-8") as f:
                if isinstance(content, (dict, list)):
                    json.dump(content, f, ensure_ascii=False, indent=2)
                else:
                    f.write(str(content or ""))
            self._send_json({"ok": True, "path": target_path, "filename": safe_name})
        except Exception as e:
            print(f"[Download to C Error] {e}\n{traceback.format_exc()}")
            self._send_error(500, f"다운로드 폴더 저장 실패: {e}")

    def _post_settings(self):
        payload = self._read_json_body()
        if payload is None:
            return
        if not isinstance(payload, dict):
            self._send_error(400, "Invalid payload format")
            return
        save_app_settings(payload)
        self._send_json({"success": True, "settings": load_app_settings()})

    def _post_clipboard(self):
        """대용량 텍스트(3~10MB JSON)를 Windows 시스템 클립보드에 초고속 다이렉트 복사."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_error(400, "Empty clipboard body")
                return
            # 대용량 payload 읽기
            raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
            
            # Content-Type이 application/json이고 {"text": "..."} 형태일 때만 파싱, 그 외(text/plain, json 파일 전체 등)는 raw를 그대로 복사
            text_to_copy = raw
            c_type = self.headers.get("Content-Type", "")
            if "application/json" in c_type and raw.strip().startswith("{"):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict) and "text" in parsed and isinstance(parsed["text"], str):
                        text_to_copy = parsed["text"]
                except Exception:
                    pass

            ok = set_windows_clipboard_text(text_to_copy)
            if ok:
                byte_len = len(text_to_copy.encode("utf-8"))
                print(f"[Clipboard] 시스템 클립보드 복사 성공: {byte_len:,} bytes ({len(text_to_copy):,} chars)")
                self._send_json({"success": True, "bytes_copied": byte_len})
            else:
                self._send_error(500, "Failed to copy to Windows clipboard")
        except Exception as e:
            print(f"[Error] _post_clipboard 예외: {e}\n{traceback.format_exc()}")
            self._send_error(500, f"Clipboard copy error: {e}")

    def _post_worldviews(self):
        payload = self._read_json_body()
        if payload is None:
            return
        if not isinstance(payload, dict):
            self._send_error(400, "Invalid payload format")
            return
        save_worldviews_config(payload)
        self._send_json({"success": True, "message": "Worldviews config saved"})

    def _post_save(self):
        payload = self._read_json_body()
        if payload is None:
            return

        filename = payload.get("path") or payload.get("filename")
        data = payload.get("data")
        if not filename or data is None:
            self._send_error(400, "Missing filename or data")
            return

        candidate_path = os.path.abspath(os.path.join(BASE_DIR, filename))
        if not os.path.exists(candidate_path) and not filename.lower().endswith(".json"):
            filename += ".json"
        if not is_safe_path(BASE_DIR, filename):
            self._send_error(403, "Invalid path")
            return

        filepath = os.path.abspath(os.path.join(BASE_DIR, filename))
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if os.path.exists(filepath):
            try:
                shutil.copy2(filepath, filepath + ".bak")
            except Exception:
                pass

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if filepath in _FILE_CHUNKS_CACHE:
            del _FILE_CHUNKS_CACHE[filepath]
        invalidate_branch_tree_cache()

        self._send_json({"success": True, "message": f"Saved to {filename}", "filename": filename})

    def _post_mkdir(self):
        payload = self._read_json_body()
        if payload is None:
            return
        rel_path = payload.get("path", "").strip()
        if not rel_path:
            self._send_error(400, "Missing folder path")
            return
        if not is_safe_path(STORAGE_DIR, rel_path):
            self._send_error(403, "Access denied")
            return
        os.makedirs(os.path.abspath(os.path.join(STORAGE_DIR, rel_path)), exist_ok=True)
        self._send_json({"success": True, "created": rel_path})

    def _post_move(self):
        payload = self._read_json_body()
        if payload is None:
            return

        source_path = payload.get("source", "").strip()
        target_folder = payload.get("target_folder", "").strip()
        if not source_path:
            self._send_error(400, "Missing source path")
            return

        # 소스 경로 해석 (root 파일 or storage 파일)
        if payload.get("from_root", False):
            if not is_safe_path(BASE_DIR, source_path):
                self._send_error(403, "Access denied")
                return
            src_full = os.path.abspath(os.path.join(BASE_DIR, source_path))
        else:
            src_full = os.path.abspath(os.path.join(STORAGE_DIR, source_path))
            if not is_safe_path(STORAGE_DIR, source_path):
                src_full = os.path.abspath(os.path.join(BASE_DIR, source_path))
                if not is_safe_path(BASE_DIR, source_path):
                    self._send_error(403, "Access denied")
                    return

        if not os.path.exists(src_full):
            self._send_error(404, "Source not found")
            return

        if not is_safe_path(STORAGE_DIR, target_folder):
            self._send_error(403, "Invalid target folder")
            return

        dest_dir = os.path.abspath(os.path.join(STORAGE_DIR, target_folder)) if target_folder else STORAGE_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest_full = os.path.join(dest_dir, os.path.basename(src_full))

        if os.path.abspath(src_full) == os.path.abspath(dest_full):
            self._send_json({"success": True, "message": "Already at destination"})
            return

        shutil.move(src_full, dest_full)
        invalidate_branch_tree_cache()
        new_rel = os.path.relpath(dest_full, STORAGE_DIR).replace("\\", "/")
        self._send_json({"success": True, "new_path": new_rel})

    def _post_rename(self):
        payload = self._read_json_body()
        if payload is None:
            return

        old_path = payload.get("old_path", "").strip()
        new_name = payload.get("new_name", "").strip()
        if not old_path or not new_name:
            self._send_error(400, "Missing parameters")
            return

        # storage/ 또는 BASE_DIR 에서 소스 탐색
        src_full = os.path.abspath(os.path.join(STORAGE_DIR, old_path))
        if not (is_safe_path(STORAGE_DIR, old_path) and os.path.exists(src_full)):
            src_full = os.path.abspath(os.path.join(BASE_DIR, old_path))
            if not is_safe_path(BASE_DIR, old_path) or not os.path.exists(src_full):
                self._send_error(404, "Target not found")
                return

        if os.path.isfile(src_full) and not new_name.lower().endswith(".json"):
            new_name += ".json"

        dest_full = os.path.join(os.path.dirname(src_full), new_name)
        os.rename(src_full, dest_full)
        invalidate_branch_tree_cache()
        self._send_json({"success": True, "new_name": new_name})

    def _post_delete(self):
        payload = self._read_json_body()
        if payload is None:
            return
        rel_path = payload.get("path", "").strip()
        if not rel_path:
            self._send_error(400, "Missing path")
            return

        target = os.path.abspath(os.path.join(STORAGE_DIR, rel_path))
        if not is_safe_path(STORAGE_DIR, rel_path) or not os.path.exists(target):
            self._send_error(404, "Not found")
            return

        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        invalidate_branch_tree_cache()
        self._send_json({"success": True, "deleted": rel_path})

    def _post_upload(self):
        payload = self._read_json_body()
        if payload is None:
            return

        target_folder = payload.get("target_folder", "").strip()
        filename = payload.get("filename", "").strip()
        data = payload.get("data")
        if not filename or data is None:
            self._send_error(400, "Missing filename or data")
            return

        if not filename.lower().endswith(".json"):
            filename += ".json"
        if not is_safe_path(STORAGE_DIR, target_folder):
            self._send_error(403, "Invalid target folder")
            return

        dest_dir = os.path.abspath(os.path.join(STORAGE_DIR, target_folder)) if target_folder else STORAGE_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, os.path.basename(filename))
        with open(dest_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        invalidate_branch_tree_cache()
        rel_p = os.path.relpath(dest_file, STORAGE_DIR).replace("\\", "/")
        self._send_json({"success": True, "path": rel_p})

    def _post_branch_off(self):
        payload = self._read_json_body()
        if payload is None:
            return

        source_path = payload.get("source_path", "").strip()
        new_filename = (payload.get("new_filename") or payload.get("target_name") or "").strip()
        target_folder = payload.get("target_folder", "").strip()
        up_to_chunk_index = payload.get("up_to_chunk_index") if payload.get("up_to_chunk_index") is not None \
                             else payload.get("fork_chunk_index")
        copy_all = payload.get("copy_all", False) or (payload.get("mode") == "full")
        data = payload.get("data")

        if not new_filename:
            self._send_error(400, "Missing new filename")
            return
        if not new_filename.lower().endswith(".json"):
            new_filename += ".json"

        # payload에 data가 없으면 source_path에서 로드
        if not data and source_path:
            src_clean = strip_storage_prefix(source_path)
            src_full = os.path.abspath(os.path.join(STORAGE_DIR, src_clean))
            if not is_safe_path(STORAGE_DIR, src_clean) or not os.path.exists(src_full):
                self._send_error(404, "Source file not found")
                return
            with open(src_full, "r", encoding="utf-8") as f:
                data = json.load(f)

        if not data:
            self._send_error(400, "Missing data or source file")
            return

        # 청크 슬라이싱
        if not copy_all and up_to_chunk_index is not None:
            try:
                cut_idx = int(up_to_chunk_index)
                chunks_ref = data.get("chunkedPrompt", {}).get("chunks")
                if isinstance(chunks_ref, list):
                    data["chunkedPrompt"]["chunks"] = chunks_ref[:cut_idx + 1]
            except (ValueError, TypeError):
                pass

        clean_folder = normalize_path(target_folder).strip("/")
        dest_rel = f"{clean_folder}/{new_filename}" if clean_folder else new_filename
        dest_full = os.path.abspath(os.path.join(STORAGE_DIR, dest_rel))
        if not is_safe_path(STORAGE_DIR, dest_rel):
            self._send_error(403, "Access denied")
            return

        os.makedirs(os.path.dirname(dest_full), exist_ok=True)
        with open(dest_full, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        total_chunks = len(data.get("chunkedPrompt", {}).get("chunks", []))
        full_path_str = f"storage/{dest_rel}"
        self._send_json({
            "success": True,
            "filename": new_filename,
            "rel_path": dest_rel,
            "full_path": full_path_str,
            "new_file": {"name": new_filename, "rel_path": dest_rel,
                         "full_path": full_path_str, "total_chunks": total_chunks},
        })

    def _post_rename_root(self):
        """BASE_DIR 루트 파일 이름 변경 (백업 파일도 함께)."""
        payload = self._read_json_body()
        if payload is None:
            return

        old_name = payload.get("old_name")
        new_name = payload.get("new_name")
        if not old_name or not new_name:
            self._send_error(400, "Missing old_name or new_name")
            return

        if not new_name.lower().endswith(".json"):
            new_name += ".json"

        old_path = os.path.join(BASE_DIR, old_name)
        new_path = os.path.join(BASE_DIR, new_name)
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            old_bak = old_path + ".bak"
            if os.path.exists(old_bak):
                try:
                    os.rename(old_bak, new_path + ".bak")
                except Exception:
                    pass

        self._send_json({"success": True, "old_name": old_name, "new_name": new_name})

    def _post_upload_font(self):
        payload = self._read_json_body()
        if payload is None:
            return

        filename = payload.get("filename")
        data_b64 = payload.get("data_base64")
        if not filename or not data_b64:
            self._send_error(400, "Missing filename or data_base64")
            return

        filename = os.path.basename(filename)
        fonts_dir = os.path.join(BASE_DIR, "fonts")
        os.makedirs(fonts_dir, exist_ok=True)
        dest_path = os.path.join(fonts_dir, filename)

        with open(dest_path, "wb") as f:
            f.write(base64.b64decode(data_b64))

        ext = os.path.splitext(filename)[1].lower()
        self._send_json({
            "success": True,
            "font": {
                "name": os.path.splitext(filename)[0],
                "filename": filename,
                "format": FONT_EXTENSIONS.get(ext, "opentype"),
                "url": f"/fonts/{urllib.parse.quote(filename)}",
            },
        })

    # ------------------------------------------------------------------
    # 공통 유틸
    # ------------------------------------------------------------------

    def _read_json_body(self) -> Optional[Any]:
        """요청 본문을 읽어 JSON으로 파싱. 실패 시 오류 응답 후 None 반환."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(body)
        except Exception as e:
            self._send_error(400, f"Invalid JSON body: {e}")
            return None

    def _send_json(self, data: Any, status_code: int = 200):
        """JSON 직렬화 후 응답 전송."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, message: str):
        """에러 JSON 응답 전송."""
        self._send_json({"error": message}, status_code=status_code)

    @staticmethod
    def _parse_float(value: str, default: float) -> float:
        """문자열을 float으로 변환. 실패 시 default 반환."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def log_message(self, fmt, *args):
        """기본 HTTP 로그를 억제하고 간결하게 출력."""
        # 정적 파일 GET은 로그 생략, API 요청만 출력
        msg = fmt % args
        if "/api/" in self.path:
            print(f"  {self.address_string()} {msg}")


# ---------------------------------------------------------------------------
# 서버 시작
# ---------------------------------------------------------------------------

def run_server():
    """서버를 시작하고 브라우저를 연다."""
    os.chdir(BASE_DIR)
    socketserver.TCPServer.allow_reuse_address = True

    port = DEFAULT_PORT
    httpd = None
    for _ in range(10):
        try:
            httpd = socketserver.TCPServer(("", port), AISHandler)
            break
        except OSError:
            port += 1

    if not httpd:
        print("[Error] 사용 가능한 포트를 찾을 수 없습니다.")
        sys.exit(1)

    url = f"http://localhost:{port}/index.html"
    print("=" * 60)
    print("  Google AI Studio Prompt and Chunk Manager")
    print(f"  Web UI  : {url}")
    print(f"  Base Dir: {BASE_DIR}")
    print("=" * 60)
    print("  브라우저를 엽니다... (종료: Ctrl+C)")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")


if __name__ == "__main__":
    run_server()

"""共通の検証 primitive。"""

from __future__ import annotations

import ast
from pathlib import Path

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]

try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[2]

class ValidationError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def read(rel_path: str) -> str:
    try:
        return (ROOT / rel_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"{rel_path} を読めません: {exc}") from exc


def load_yaml(rel_path: str) -> object:
    require(yaml is not None, "YAML 検証には PyYAML が必要です。")
    try:
        return yaml.safe_load((ROOT / rel_path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # type: ignore[union-attr]
        raise ValidationError(f"{rel_path} の YAML parse に失敗しました: {exc}") from exc


def mapping(value: object, label: str) -> dict[str, object]:
    require(isinstance(value, dict), f"{label} は mapping にしてください。")
    return value  # type: ignore[return-value]


def sequence(value: object, label: str) -> list[object]:
    require(isinstance(value, list), f"{label} は list にしてください。")
    return value  # type: ignore[return-value]


def require_keys(value: dict[str, object], keys: set[str] | tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in value]
    require(not missing, f"{label} に必要な field がありません: " + ", ".join(missing))


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    missing = [token for token in tokens if token not in text]
    require(not missing, f"{label} に必要な語がありません: " + ", ".join(missing))


def python_string_set_constant(rel_path: str, constant_name: str) -> set[str]:
    tree = ast.parse(read(rel_path), filename=rel_path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == constant_name for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        require(isinstance(value, set) and all(isinstance(item, str) for item in value), f"{rel_path}.{constant_name} は str set にしてください。")
        return set(value)
    raise ValidationError(f"{rel_path}.{constant_name} が見つかりません。")

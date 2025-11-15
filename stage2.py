import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import toml as toml_fallback


@dataclass
class AppConfig:
    package_name: str
    repo_url: str
    test_repo_mode: str
    version: str
    graph_image: str
    ascii_tree: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        section = data.get("app")
        if not isinstance(section, dict):
            raise ValueError("В config.toml должна быть секция [app]")

        def require(key: str) -> Any:
            """Достаёт обязательный параметр из секции [app]."""
            if key not in section:
                raise ValueError(f"Отсутствует обязательный параметр: {key}")
            return section[key]

        package_name = str(require("package_name"))
        repo_url = str(require("repo_url"))
        test_repo_mode = str(require("test_repo_mode"))
        version = str(require("version"))
        graph_image = str(require("graph_image"))
        ascii_tree_raw = require("ascii_tree")

        if test_repo_mode not in {"remote", "file"}:
            raise ValueError("test_repo_mode должен быть 'remote' или 'file'")

        # Приводим ascii_tree к bool
        if isinstance(ascii_tree_raw, bool):
            ascii_tree = ascii_tree_raw
        else:
            ascii_tree = str(ascii_tree_raw).lower() in {"1", "true", "yes", "on"}

        # Важно: передаём ВСЕ поля, объявленные в классе
        return cls(
            package_name=package_name,
            repo_url=repo_url,
            test_repo_mode=test_repo_mode,
            version=version,
            graph_image=graph_image,
            ascii_tree=ascii_tree,
        )


def load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {path}")

    content = path.read_bytes()
    # Если есть fallback-библиотека toml — используем её
    if "toml_fallback" in globals() and toml_fallback is not None:
        return toml_fallback.loads(content.decode("utf-8"))  # type: ignore
    # Если ни то, ни другое не доступно — даём понятную ошибку
    raise RuntimeError(
        "Не удалось импортировать парсер TOML. "
        "Используйте Python 3.11+ или установите пакет 'toml'."
    )


def find_cargo_toml(repo_spec: str) -> Path:
    """
    Находит файл Cargo.toml по строке из конфигурации.

    Варианты:
    - если repo_spec — директория, ищем в ней Cargo.toml;
    - если repo_spec — файл, считаем, что это и есть Cargo.toml.

    :param repo_spec: путь к каталогу или файлу
    :return: путь к найденному Cargo.toml
    """
    path = Path(repo_spec)
    if path.is_dir():
        candidate = path / "Cargo.toml"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"В каталоге {path} не найден Cargo.toml")
    if path.is_file():
        return path
    raise FileNotFoundError(
        f"Не удалось интерпретировать repo_url как локальный путь: {repo_spec}"
    )


def extract_direct_dependencies(cargo_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Извлекает прямые зависимости пакета из данных Cargo.toml.

    Ожидается секция [dependencies].

    Формат возвращаемого словаря:
    имя_пакета -> строка-описание версии или спецификации.

    :param cargo_data: словарь с содержимым Cargo.toml
    :return: словарь прямых зависимостей
    """
    deps = cargo_data.get("dependencies", {})
    if not isinstance(deps, dict):
        return {}

    result: Dict[str, str] = {}
    for name, spec in deps.items():
        # Простой случай: зависимость указана строкой "1.0"
        if isinstance(spec, str):
            result[name] = spec
        # Сложный случай: зависимость описана объектом { version = "...", ... }
        elif isinstance(spec, dict):
            version = spec.get("version")
            if isinstance(version, str):
                result[name] = version
            else:
                # Например, git = "..." или path = "..."
                result[name] = "<non-version spec>"
        else:
            # На всякий случай — приводим к строке
            result[name] = str(spec)
    return result


def main(argv: list[str] | None = None) -> int:
    """
    Точка входа для этапа 2.

    Алгоритм:
    1. Читаем config.toml.
    2. Находим Cargo.toml (по repo_url).
    3. Извлекаем прямые зависимости.
    4. Печатаем их на экран.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        print("Использование: python stage2_collect.py <путь к config.toml>")
        return 1

    config_path = Path(argv[0])
    try:
        raw_cfg = load_toml(config_path)
        cfg = AppConfig.from_dict(raw_cfg)
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}", file=sys.stderr)
        return 2

    # В учебной версии используем только локальный режим file
    if cfg.test_repo_mode == "remote":
        print(
            "Режим 'remote' не реализован в учебном прототипе. "
            "Используйте test_repo_mode='file' и локальный путь к Cargo.toml.",
            file=sys.stderr,
        )
        return 3

    try:
        cargo_path = find_cargo_toml(cfg.repo_url)
        cargo_data = load_toml(cargo_path)
    except Exception as e:
        print(f"Ошибка загрузки Cargo.toml: {e}", file=sys.stderr)
        return 4

    # Дополнительная проверка — совпадает ли имя и версия пакета
    pkg = cargo_data.get("package", {})
    if isinstance(pkg, dict):
        cargo_name = pkg.get("name")
        cargo_version = pkg.get("version")
        if cargo_name and cargo_name != cfg.package_name:
            print(
                f"Предупреждение: имя пакета в Cargo.toml ({cargo_name}) "
                f"отличается от package_name в config.toml ({cfg.package_name})",
                file=sys.stderr,
            )
        if cargo_version and cargo_version != cfg.version:
            print(
                f"Предупреждение: версия пакета в Cargo.toml ({cargo_version}) "
                f"отличается от version в config.toml ({cfg.version})",
                file=sys.stderr,
            )

    deps = extract_direct_dependencies(cargo_data)

    print(f"Прямые зависимости пакета {cfg.package_name} (версия {cfg.version}):")
    if not deps:
        print("  (зависимостей не найдено)")
    else:
        for name, spec in deps.items():
            print(f"  {name} -> {spec}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

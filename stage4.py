import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import toml as toml_fallback
from graph_core import DependencyGraph



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


def main(argv: list[str] | None = None) -> int:
    """
    Точка входа для этапа 4.

    Алгоритм:
    1. Считать конфиг.
    2. Загрузить тестовый граф из файла.
    3. Вычислить порядок загрузки зависимостей (load_order).
    4. Вывести его на экран.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        print("Использование: python stage4_load_order.py <путь к config.toml>")
        return 1

    config_path = Path(argv[0])

    try:
        raw_cfg = load_toml(config_path)
        cfg = AppConfig.from_dict(raw_cfg)
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}", file=sys.stderr)
        return 2

    if cfg.test_repo_mode != "file":
        print(
            "Для демонстрации этапа 4 реализован только тестовый режим "
            "test_repo_mode='file' с файлом описания графа.",
            file=sys.stderr,
        )
        return 3

    test_repo_path = Path(cfg.repo_url)
    try:
        graph = DependencyGraph.from_test_file(test_repo_path)
    except Exception as e:
        print(f"Ошибка загрузки тестового репозитория: {e}", file=sys.stderr)
        return 4

    # Вычисляем порядок загрузки зависимостей
    order = graph.load_order(cfg.package_name)
    if not order:
        print(f"Пакет {cfg.package_name} не найден в тестовом репозитории.")
        return 0

    print("Порядок загрузки зависимостей (приблизительный топологический порядок):")
    for i, name in enumerate(order, start=1):
        print(f"{i}. {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

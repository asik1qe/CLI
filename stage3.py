import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import toml as toml_fallback
from graph_core import DependencyGraph, ascii_tree


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

        # Преобразуем ascii_tree к логическому типу
        if isinstance(ascii_tree_raw, bool):
            ascii_tree = ascii_tree_raw
        else:
            ascii_tree = str(ascii_tree_raw).lower() in {"1", "true", "yes", "on"}

        # ВАЖНО — передаём ВСЕ поля, иначе AppConfig упадёт
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


def build_graph_from_test_repo(path: Path) -> DependencyGraph:
    """
    Строит граф зависимостей из файла тестового репозитория.

    Формат файла соответствует функции DependencyGraph.from_test_file().
    """
    return DependencyGraph.from_test_file(path)


def main(argv: list[str] | None = None) -> int:
    """
    Точка входа для этапа 3.

    Алгоритм:
    1. Считать конфиг.
    2. Загрузить тестовый репозиторий и построить граф.
    3. Выполнить BFS-обход от корневого пакета.
    4. Вывести граф зависимостей и ASCII-дерево.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        print("Использование: python stage3_graph.py <путь к config.toml>")
        return 1

    config_path = Path(argv[0])

    try:
        raw_cfg = load_toml(config_path)
        cfg = AppConfig.from_dict(raw_cfg)
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}", file=sys.stderr)
        return 2

    # Для демонстрации реализован только тестовый режим с файлом
    if cfg.test_repo_mode != "file":
        print(
            "Для демонстрации этапа 3 реализован только тестовый режим "
            "test_repo_mode='file' с файлом описания графа.",
            file=sys.stderr,
        )
        return 3

    test_repo_path = Path(cfg.repo_url)
    try:
        graph = build_graph_from_test_repo(test_repo_path)
    except Exception as e:
        print(f"Ошибка загрузки тестового репозитория: {e}", file=sys.stderr)
        return 4

    # Получаем подграф зависимостей, достижимых из корня
    subgraph = graph.bfs_dependencies(cfg.package_name)
    if not subgraph:
        print(f"Пакет {cfg.package_name} не найден в тестовом репозитории.")
        return 0

    # Печатаем список смежности подграфа
    print("Граф зависимостей (транзитивно, алгоритм BFS без рекурсии):")
    for src, targets in sorted(subgraph.items()):
        if targets:
            deps_str = ", ".join(sorted(targets))
        else:
            deps_str = "(нет зависимостей)"
        print(f"  {src} -> {deps_str}")

    # Печатаем ASCII-дерево
    print("\nASCII-дерево зависимостей:")
    print(ascii_tree(graph, cfg.package_name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

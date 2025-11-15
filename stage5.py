import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import toml as toml_fallback

try:
    import graphviz  # type: ignore
except ModuleNotFoundError:
    graphviz = None  # type: ignore

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

        # Приведение ascii_tree к bool
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


def ensure_svg_filename(name: str) -> str:
    """
    Гарантирует, что имя файла оканчивается на .svg.

    Если передано 'deps', вернётся 'deps.svg'.
    Если 'deps.png' — станет 'deps.svg'.
    """
    path = Path(name)
    if path.suffix.lower() != ".svg":
        path = path.with_suffix(".svg")
    return str(path)


def render_to_svg(dot_source: str, svg_path: str) -> None:
    """
    Пытается сохранить SVG-граф на основе DOT-описания.

    Если установлен пакет python-graphviz:
        - создаёт объект graphviz.Source и рендерит в формат SVG.
    Если нет:
        - сохраняет только .dot-файл и выводит инструкцию,
          как вручную получить SVG через утилиту dot.

    :param dot_source: текст в формате Graphviz (DOT)
    :param svg_path: желаемое имя файла SVG (с расширением или без)
    """
    svg_path = ensure_svg_filename(svg_path)
    base, _ = os.path.splitext(svg_path)

    if graphviz is None:
        # Если нет библиотеки graphviz — сохраняем только .dot
        dot_path = base + ".dot"
        Path(dot_path).write_text(dot_source, encoding="utf-8")
        print(
            "Предупреждение: пакет 'graphviz' для Python не установлен.\n"
            f"Сохранён только файл {dot_path}. "
            "Для получения SVG выполните:\n"
            f'  dot -Tsvg "{dot_path}" -o "{svg_path}"'
        )
        return

    # Если библиотека есть — рисуем SVG автоматически
    src = graphviz.Source(dot_source)
    src.format = "svg"
    rendered = src.render(base, cleanup=True)
    print(f"SVG-граф сохранён в файле: {rendered}")


def main(argv: list[str] | None = None) -> int:
    """
    Точка входа для этапа 5.

    Алгоритм:
    1. Считать config.toml.
    2. Загрузить граф из тестового репозитория (text-файл с описанием зависимостей).
    3. Сгенерировать DOT-описание графа.
    4. Сохранить/отрендерить SVG-файл.
    5. При необходимости вывести ASCII-дерево.
    """
    # Если argv не передан — берём реальные аргументы командной строки
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        print("Использование: python stage5.py <путь к config.toml>")
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
            "Для демонстрации этапа 5 визуализация делается по тестовому репозиторию "
            "(test_repo_mode='file').",
            file=sys.stderr,
        )
        return 3

    # repo_url указывает на файл тестового репозитория, например test_repo.txt
    test_repo_path = Path(cfg.repo_url)
    try:
        graph = DependencyGraph.from_test_file(test_repo_path)
    except Exception as e:
        print(f"Ошибка загрузки тестового репозитория: {e}", file=sys.stderr)
        return 4

    # Получаем DOT-описание графа от корневого пакета
    dot = graph.to_graphviz(root=cfg.package_name)
    print("Описание графа в формате Graphviz (DOT):")
    print(dot)

    # Пытаемся отрендерить SVG
    render_to_svg(dot, cfg.graph_image)

    # Если в конфиге включен режим ASCII-дерева — выводим его
    if cfg.ascii_tree:
        print("\nASCII-дерево зависимостей:")
        print(ascii_tree(graph, cfg.package_name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

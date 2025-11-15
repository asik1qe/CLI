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
        """
        Создаёт объект AppConfig из словаря, полученного из TOML.

        :param data: словарь с данными из config.toml
        :return: AppConfig с валидированными полями
        """
        # Ожидаем наличие секции [app] в TOML
        section = data.get("app")
        if not isinstance(section, dict):
            raise ValueError("В config.toml должна быть секция [app]")

        # Вспомогательная функция: достать обязательный параметр
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

        # Приводим ascii_tree к bool
        if isinstance(ascii_tree_raw, bool):
            ascii_tree = ascii_tree_raw
        elif isinstance(ascii_tree_raw, (int, str)):
            ascii_tree = str(ascii_tree_raw).lower() in {"1", "true", "yes", "on"}
        else:
            raise ValueError("ascii_tree должен быть булевым или строкой")

        # Проверяем корректность режима работы
        if test_repo_mode not in {"remote", "file"}:
            raise ValueError("test_repo_mode должен быть 'remote' или 'file'")

        return cls(
            package_name=package_name,
            repo_url=repo_url,
            test_repo_mode=test_repo_mode,
            version=version,
            graph_image=graph_image,
            ascii_tree=ascii_tree,
        )

    def as_key_value(self) -> Dict[str, str]:
        """
        Возвращает параметры конфигурации в виде словаря строк,
        чтобы удобно печатать их в формате key=value.

        :return: словарь "ключ -> строковое значение"
        """
        return {
            "package_name": self.package_name,
            "repo_url": self.repo_url,
            "test_repo_mode": self.test_repo_mode,
            "version": self.version,
            "graph_image": self.graph_image,
            "ascii_tree": str(self.ascii_tree).lower(),
        }


def load_toml(path: Path) -> Dict[str, Any]:
    """
    Загружает и парсит TOML-файл по указанному пути.

    Использует встроенный tomllib (если есть) или внешнюю библиотеку toml.

    :param path: путь к файлу TOML
    :return: словарь с содержимым файла
    """
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
    Точка входа для этапа 1.

    Сценарий работы:
    1. Читает путь к config.toml из аргументов командной строки.
    2. Загружает и валидирует конфигурацию.
    3. Выводит все параметры в формате key=value.
    """
    # Если argv не передан явно — берём sys.argv[1:]
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        print("Использование: python stage1_config.py <путь к config.toml>")
        return 1

    config_path = Path(argv[0])

    try:
        raw = load_toml(config_path)
        cfg = AppConfig.from_dict(raw)
    except Exception as e:
        # Любая ошибка конфигурации — печатаем и выходим с кодом 2
        print(f"Ошибка при чтении конфигурации: {e}", file=sys.stderr)
        return 2

    # Печатаем параметры в формате ключ=значение
    for key, value in cfg.as_key_value().items():
        print(f"{key}={value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

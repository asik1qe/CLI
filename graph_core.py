from __future__ import annotations
from collections import deque, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Set


@dataclass
class DependencyGraph:
    """
    Класс ориентированного графа зависимостей.
    Ребро A -> B означает: пакет A зависит от пакета B.
    """

    # adjacency хранит список смежности: имя пакета -> множество зависимостей
    adjacency: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_edge(self, src: str, dst: str) -> None:
        """
        Добавляет ориентированное ребро src -> dst в граф.

        :param src: пакет-источник (кто зависит)
        :param dst: пакет-цель (от кого зависит)
        """
        # Добавляем зависимость dst к src
        self.adjacency[src].add(dst)
        # Гарантируем, что dst тоже есть в словаре adjacency
        self.adjacency.setdefault(dst, set())

    @classmethod
    def from_edges(cls, edges: Iterable[tuple[str, str]]) -> "DependencyGraph":
        """
        Создает граф из списка рёбер.

        :param edges: итерируемый объект пар (src, dst)
        :return: объект DependencyGraph
        """
        g = cls()
        for src, dst in edges:
            g.add_edge(src, dst)
        return g

    @classmethod
    def from_test_file(cls, path: Path) -> "DependencyGraph":
        """
        Строит граф зависимостей из "тестового репозитория" — текстового файла.

        Формат файла:
            # комментарии начинаются с #
            A: B C D
            B: D
            C:

        Левая часть до двоеточия — имя пакета.
        Правая часть — список пакетов, от которых он зависит (через пробел).

        :param path: путь к текстовому файлу с описанием графа
        :return: объект DependencyGraph
        """
        if not path.exists():
            raise FileNotFoundError(f"Файл тестового репозитория не найден: {path}")

        g = cls()
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            # Пустые строки и комментарии пропускаем
            if not line or line.startswith("#"):
                continue
            # В строке обязательно должен быть символ ':'
            if ":" not in line:
                raise ValueError(f"Неверный формат строки в тестовом репозитории: {line}")
            left, right = line.split(":", 1)
            src = left.strip()
            deps_str = right.strip()
            if not deps_str:
                # Пакет без зависимостей, просто регистрируем его
                g.adjacency.setdefault(src, set())
                continue
            # Разбиваем правую часть по пробелам
            deps = [d.strip() for d in deps_str.split() if d.strip()]
            for dst in deps:
                g.add_edge(src, dst)
        return g

    def bfs_dependencies(self, root: str) -> Dict[str, Set[str]]:
        """
        Строит подграф всех зависимостей, достижимых из root,
        с помощью обхода в ширину (BFS) без рекурсии.

        :param root: имя корневого пакета
        :return: словарь "пакет -> множество его зависимостей", только для reachable-узлов
        """
        # Если корня нет в графе — возвращаем пустой словарь
        if root not in self.adjacency:
            return {}

        visited: Set[str] = set()   # уже посещённые вершины
        order: List[str] = []       # порядок обхода
        queue: deque[str] = deque([root])  # очередь для BFS

        # Классический BFS
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            # Добавляем в очередь всех ещё не посещённых соседей
            for neigh in self.adjacency.get(node, ()):
                if neigh not in visited:
                    queue.append(neigh)

        # Формируем подграф только по посещённым вершинам
        subgraph: Dict[str, Set[str]] = {}
        for node in order:
            subgraph[node] = set(self.adjacency.get(node, set())) & visited
        return subgraph

    def reverse_dependencies(self) -> "DependencyGraph":
        """
        Строит граф обратных зависимостей.

        Если A -> B (A зависит от B),
        в обратном графе будет B -> A (от B зависит A).

        :return: новый DependencyGraph с рёбрами в обратном направлении
        """
        rev = DependencyGraph()
        for src, targets in self.adjacency.items():
            # Если исходящих рёбер нет — всё равно добавляем вершину
            if not targets:
                rev.adjacency.setdefault(src, set())
            for dst in targets:
                # Переворачиваем ребро на обратное
                rev.add_edge(dst, src)
        return rev

    def load_order(self, root: str) -> List[str]:
        """
        Вычисляет порядок загрузки зависимостей для указанного пакета.
        По сути — топологическая сортировка reachable-подграфа.

        Используется модификация алгоритма Кана:
        - считаем входящие степени вершин;
        - начинаем с вершин с нулевой степенью;
        - постепенно "удаляем" рёбра и добавляем новые вершины в очередь.

        Если в графе есть циклы, полный топологический порядок невозможен,
        поэтому оставшиеся вершины просто добавляются в конец списка.

        :param root: имя корневого пакета
        :return: список имён пакетов в порядке загрузки
        """
        # Берём только reachable-подграф
        reachable = self.bfs_dependencies(root)
        if not reachable:
            return []

        # Считаем входящую степень для каждой вершины
        indegree: Dict[str, int] = {v: 0 for v in reachable}
        for src, targets in reachable.items():
            for dst in targets:
                indegree[dst] += 1

        # В очередь кладём все вершины без входящих рёбер
        queue: deque[str] = deque([v for v, deg in indegree.items() if deg == 0])
        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            # "Удаляем" рёбра из node и уменьшаем входящую степень соседей
            for neigh in reachable.get(node, ()):
                indegree[neigh] -= 1
                # Если степень стала 0 — можно загружать
                if indegree[neigh] == 0:
                    queue.append(neigh)

        # Если порядок короче числа вершин — есть цикл
        if len(order) < len(indegree):
            # Добавляем оставшиеся вершины в произвольном порядке
            for v in indegree:
                if v not in order:
                    order.append(v)

        return order

    def to_graphviz(self, root: str | None = None) -> str:
        """
        Генерирует описание графа в формате DOT (Graphviz).

        :param root: если задан, берём только вершины, достижимые из root;
                     если None — берём весь граф целиком.
        :return: строка с описанием графа в формате Graphviz
        """
        if root is not None:
            # Ограничиваемся reachable-подграфом от root
            sub = self.bfs_dependencies(root)
            nodes = sub.keys()
        else:
            # Используем весь граф
            sub = self.adjacency
            nodes = self.adjacency.keys()

        lines = ["digraph deps {"]
        for node in nodes:
            # Если у вершины нет исходящих рёбер — просто выводим её как одиночную
            if node not in sub or not sub[node]:
                lines.append(f'    "{node}";')
            else:
                # Иначе выводим все рёбра node -> dst
                for dst in sub[node]:
                    lines.append(f'    "{node}" -> "{dst}";')
        lines.append("}")
        return "\n".join(lines)


def ascii_tree(graph: DependencyGraph, root: str) -> str:
    """
    Строит человекочитаемое ASCII-дерево зависимостей из корня root.

    Важный момент: дерево строится по графу, в котором возможны циклы.
    Чтобы избежать бесконечной рекурсии, повторные вершины помечаются "(...)"
    и не обходятся повторно.

    :param graph: объект DependencyGraph
    :param root: корневой пакет
    :return: строка с ASCII-деревом
    """
    if root not in graph.adjacency:
        return f"{root} (нет в графе)"

    lines: List[str] = []
    visited: Set[str] = set()

    def walk(node: str, prefix: str, is_last: bool) -> None:
        """
        Внутренняя рекурсивная функция для обхода графа и построения дерева.

        :param node: текущая вершина
        :param prefix: префикс для отрисовки отступов и вертикальных линий
        :param is_last: является ли вершина последней в своём списке детей
        """
        # Выбираем "соединитель" ветки — последний элемент или нет
        connector = "└── " if is_last else "├── "
        if prefix:
            line_prefix = prefix + connector
        else:
            line_prefix = ""

        # Если вершина уже была посещена — рисуем её как повтор и выходим
        if node in visited:
            lines.append(f"{line_prefix}{node} (...)")
            return

        # Добавляем текущую вершину в вывод
        lines.append(f"{line_prefix}{node}")
        visited.add(node)

        # Сортируем детей для стабильного порядка вывода
        children = sorted(graph.adjacency.get(node, []))
        for i, child in enumerate(children):
            last_child = i == len(children) - 1
            # Формируем префикс для следующего уровня
            next_prefix = prefix + ("    " if is_last else "│   ")
            walk(child, next_prefix, last_child)

    # Запускаем обход от корня как единственной верхней ветки
    walk(root, "", True)
    return "\n".join(lines)

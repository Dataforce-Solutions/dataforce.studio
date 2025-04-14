from promptopt.dataclasses import Exmaple
from promptopt.graph import Graph
from abc import ABC, abstractmethod


class BaseOptimizer(ABC):
    def __init__(self, graph: Graph) -> None:
        self.geraph = graph

    @abstractmethod
    async def optimize(self, examples: list[Exmaple]) -> None:
        pass

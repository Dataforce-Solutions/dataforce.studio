from promptopt.optimizers._base import BaseOptimizer
from promptopt.dataclasses import Example
from promptopt.graph import Graph
from promptopt.trace import Trace
from promptopt.llm import LLM

import random


class RandomFewShotOptimizer(BaseOptimizer):
    def __init__(
        self,
        graph: Graph,
        max_training_examples: int,
        max_examples_per_node: int,
        llm: LLM,
    ) -> None:
        self.graph = graph
        self.llm = llm

        self.max_training_examples = max_training_examples
        self.max_examples_per_node = max_examples_per_node

    async def optimize(self, examples: list[Example]) -> None:
        if len(examples) > self.max_training_examples:
            training_examples = random.sample(examples, self.max_training_examples)
        else:
            training_examples = examples[:]

        trace = Trace()

        # TODO: parallelize and collect
        for example in training_examples:
            await self.graph.run(example.input, self.llm, trace)

        for node in self.graph.nodes.values():
            if id(node) in trace._examples:
                node_examples = trace._examples[id(node)]
                random.shuffle(examples)
                examples = examples[: self.max_examples_per_node]
                node.set_examples(node_examples)

        print(trace)

        for node_name, node in self.graph.nodes.items():
            print(f"{node_name} -> ", node._examples)

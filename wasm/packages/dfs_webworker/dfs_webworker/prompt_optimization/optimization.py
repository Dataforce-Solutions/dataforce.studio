from promptopt.graph import Graph
from promptopt.llm import LLM
from promptopt.dataclasses import Example
from promptopt.optimizers.few_shot import RandomFewShotOptimizer
from promptopt.optimizers.jedi import JEDIOptimizer


SMALL_SIZE_THRESHOLD = 64

async def _optimize_zero_shot(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
) -> None:
    # TODO
    return


async def _optimize_small(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
) -> None:
    # TODO: Optimize the instruction first -> then the examples
    optimizer = RandomFewShotOptimizer(
        graph=graph,
        max_training_examples=64,
        max_examples_per_node=8,
        llm=student,
    )
    await optimizer.optimize(dataset)


async def _optimize_large(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
) -> None:
    optimizer = JEDIOptimizer(
        graph=graph,
        student=student,
        teacher=teacher,
        train_fraction=0.75,
        max_training_examples=256,
        max_examples_per_node=8,
        max_validation_batch_size=64,
        n_instructions_to_propose=10,
        task_description=task_description,
    )
    await optimizer.optimize(dataset)


async def optimize(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
) -> None:
    if len(dataset) < 1:
        await _optimize_zero_shot(
            student=student,
            teacher=teacher,
            graph=graph,
            dataset=dataset,
            task_description=task_description,
        )
    elif len(dataset) < SMALL_SIZE_THRESHOLD:
        await _optimize_small(
            student=student,
            teacher=teacher,
            graph=graph,
            dataset=dataset,
            task_description=task_description,
        )
    else:
        await _optimize_large(
            student=student,
            teacher=teacher,
            graph=graph,
            dataset=dataset,
            task_description=task_description,
        )

from dataclasses import dataclass

from dfs_webworker.utils import success
from dfs_webworker.store import Store
from dfs_webworker.prompt_optimization.jsdata import JsData
from dfs_webworker.prompt_optimization.utils import (
    jsdata_to_graph,
    init_llm,
    data_to_examples,
)
from dfs_webworker.prompt_optimization.optimization import optimize
from promptopt.graph import Graph
from promptopt.llm import LLM


@dataclass
class StoredGraph:
    graph: Graph
    llm: LLM


async def prompt_optimization_train(task_spec: dict):
    data = JsData.from_dict(task_spec)
    graph = jsdata_to_graph(data)

    student = init_llm(data.settings.student)
    teacher = init_llm(data.settings.teacher)
    examples = data_to_examples(
        data.dataset,
        inputs=data.settings.inputs,
        outputs=data.settings.outputs,
    )
    print(f"Examples: {examples}")
    print(f"Graph: {graph.llm_repr()}")

    await optimize(
        student=student,
        teacher=teacher,
        graph=graph,
        dataset=data_to_examples(
            data.dataset,
            inputs=data.settings.inputs,
            outputs=data.settings.outputs,
        ),
        task_description=data.settings.task_description,
        evaluation_mode=data.settings.evaluation_mode,
        criteria_list=data.settings.criteria_list,
    )

    model_id = Store.save(StoredGraph(graph=graph, llm=student))

    return success(model_id=model_id, model="<TODO_BINARY_MODEL>")


async def prompt_optimization_predict(model_id: str, data: dict[str, list]):
    model = Store.get(model_id)

    if not isinstance(model, StoredGraph):
        raise ValueError(f"Model {model_id} is not a valid StoredGraph model")

    graph = model.graph
    llm = model.llm

    keys = list(data.keys())
    values_list = [dict(zip(keys, v)) for v in zip(*data.values())]

    # TODO - parallelize this
    predictions = [await graph.run(inputs=d, llm=llm) for d in values_list]

    return success(predictions=predictions)

from dataclasses import dataclass

from dfs_webworker.utils import success
from dfs_webworker.store import Store

from promptopt.dataclasses import Field as NativeField
from promptopt.graph import Graph, BaseNode, InputNode, OutputNode, Processor, Gate
from promptopt.llm import OpenAIProvider, LLM


@dataclass
class Field:
    id: str
    value: str
    variant: str
    type: str | None = None
    variadic: bool = False


@dataclass
class NodeData:
    fields: list[Field]
    type: str
    hint: str | None = None


@dataclass
class Node:
    id: str
    data: NodeData


@dataclass
class Edge:
    id: str
    source_node: str
    source_field: str
    source_field_name: str
    target_field_name: str
    target_node: str
    target_field: str


@dataclass
class GraphData:
    edges: list[Edge]
    nodes: list[Node]


@dataclass
class ProviderSettings:
    api_key: str
    organization: str | None = None
    api_base: str | None = None


@dataclass
class Provider:
    provider_id: str
    model_id: str
    provider_settings: ProviderSettings


@dataclass
class Settings:
    task_description: str
    teacher: Provider
    student: Provider
    evaluation_mode: str
    criteria_list: list[str]


@dataclass
class JsData:
    data: GraphData
    settings: Settings
    dataset: None = None  # TODO

    @classmethod
    def from_dict(cls, raw: dict) -> "JsData":
        def parse_field(field: dict) -> Field:
            return Field(**field)

        def parse_node_data(data: dict) -> NodeData:
            fields = [parse_field(f) for f in data["fields"]]
            return NodeData(fields=fields, type=data["type"], hint=data.get("hint"))

        def parse_node(node: dict) -> Node:
            return Node(id=node["id"], data=parse_node_data(node["data"]))

        def parse_edge(edge: dict) -> Edge:
            source_field_id = edge["sourceField"]
            target_field_id = edge["targetField"]

            def get_field_value(node_id: str, field_id: str) -> str:
                for node in raw["data"]["nodes"]:
                    if node["id"] == node_id:
                        for field in node["data"]["fields"]:
                            if field["id"] == field_id:
                                return field.get("value", "")
                return ""

            return Edge(
                id=edge["id"],
                source_node=edge["sourceNode"],
                source_field=source_field_id,
                target_node=edge["targetNode"],
                target_field=target_field_id,
                source_field_name=get_field_value(edge["sourceNode"], source_field_id),
                target_field_name=get_field_value(edge["targetNode"], target_field_id),
            )

        def parse_graph_data(data: dict) -> GraphData:
            edges = [parse_edge(e) for e in data["edges"]]
            nodes = [parse_node(n) for n in data["nodes"]]
            return GraphData(edges=edges, nodes=nodes)

        def parse_provider_settings(settings: dict) -> ProviderSettings:
            return ProviderSettings(
                api_key=settings["apiKey"],
                organization=settings.get("organization"),
                api_base=settings.get("apiBase"),
            )

        def parse_provider(provider: dict) -> Provider:
            return Provider(
                provider_id=provider["providerId"],
                model_id=provider["modelId"],
                provider_settings=parse_provider_settings(provider["providerSettings"]),
            )

        def parse_settings(settings: dict) -> Settings:
            return Settings(
                task_description=settings["taskDescription"],
                teacher=parse_provider(settings["teacher"]),
                student=parse_provider(settings["student"]),
                evaluation_mode=settings["evaluationMode"],
                criteria_list=settings["criteriaList"],
            )

        return cls(
            data=parse_graph_data(raw["data"]),
            settings=parse_settings(raw["settings"]),
        )


@dataclass
class StoredGraph:
    graph: Graph
    llm: LLM


def convert_js_field(js_field) -> NativeField:
    return NativeField(
        name=js_field.value,
        type=js_field.type,
        is_variadic=js_field.variadic,
        allowed_values=None,
    )


def jsdata_to_graph(js_data: JsData) -> Graph:
    graph = Graph()
    node_map: dict[str, BaseNode] = {}

    for node in js_data.data.nodes:
        node_type = node.data.type.lower()
        fields = node.data.fields

        if node_type == "input":
            node_obj = InputNode([convert_js_field(f) for f in fields])

        elif node_type == "output":
            node_obj = OutputNode([convert_js_field(f) for f in fields])

        elif node_type == "processor":
            input_fields = [convert_js_field(f) for f in fields if f.variant == "input"]
            output_fields = [
                convert_js_field(f) for f in fields if f.variant == "output"
            ]
            node_obj = Processor(input_fields, output_fields)

        elif node_type == "gate":
            classification_fields = [
                convert_js_field(f) for f in fields if f.variant == "output"
            ]
            if len(classification_fields) != 1:
                raise ValueError(
                    f"Gate node {node.id} must have exactly one classification field"
                )
            output_classes = [f.value for f in fields if f.variant == "condition"]
            node_obj = Gate(
                classification_field=classification_fields[0],
                output_classes=output_classes,
            )

        else:
            raise ValueError(f"Unknown node type: {node.data.type}")

        print("adding node", node.id, node_type)
        graph.add_node(node_obj, node_name=node.id)
        node_map[node.id] = node_obj

    for edge in js_data.data.edges:
        lhs_node = node_map[edge.source_node]
        rhs_node = node_map[edge.target_node]
        graph.connect(
            lhs_node, edge.source_field_name, rhs_node, edge.target_field_name
        )

    return graph


async def prompt_optimization_train(task_spec: dict):
    data = JsData.from_dict(task_spec)
    graph = jsdata_to_graph(data)

    student = data.settings.student

    if student.provider_id == "openAi":
        llm = OpenAIProvider(
            api_key=student.provider_settings.api_key, model=student.model_id
        )

    # elif student.provider_id == "ollama":
    #     pass

    else:
        # TODO
        raise ValueError(f"Unsupported provider: {student.provider_id}")

    model_id = Store.save(StoredGraph(graph=graph, llm=llm))

    return success(model_id=model_id, model="<TODO_BINARY_MODEL>")


async def prompt_optimization_predict(model_id: str, data: list[dict]):
    model = Store.get(model_id)

    if not isinstance(model, StoredGraph):
        raise ValueError(f"Model {model_id} is not a valid StoredGraph model")

    graph = model.graph
    llm = model.llm

    # TODO - parallelize this
    predictions = [await graph.run(inputs=d, llm=llm) for d in data]

    return success(predictions=predictions)

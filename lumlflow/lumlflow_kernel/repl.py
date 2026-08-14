from __future__ import annotations

import ast
import contextlib
import io
from collections.abc import Callable
from typing import Any

ValueDescriptor = dict[str, str]
ValueLoader = Callable[[ValueDescriptor], Any]
IntegrityChecker = Callable[[ValueDescriptor], None]
PreviewBuilder = Callable[[Any], dict[str, Any]]


class ScratchEvaluator:
    def __init__(
        self,
        branch_slice: dict[str, ValueDescriptor],
        load_value: ValueLoader,
    ) -> None:
        self._load_value = load_value
        self._by_cell: dict[str, dict[str, ValueDescriptor]] = {}
        self._by_output: dict[str, list[tuple[str, ValueDescriptor]]] = {}
        self._touched: list[tuple[str, ValueDescriptor]] = []
        self._touched_names: set[str] = set()
        for qualified_name, descriptor in branch_slice.items():
            slug, separator, output = qualified_name.partition(".")
            if not separator or not slug or not output:
                raise ValueError("branch slice names must use slug.output")
            self._by_cell.setdefault(slug, {})[output] = descriptor
            self._by_output.setdefault(output, []).append((qualified_name, descriptor))

    @property
    def touched(self) -> list[str]:
        return [name for name, _descriptor in self._touched]

    def execute(
        self,
        code: str,
        preview_builder: PreviewBuilder | None = None,
    ) -> dict[str, object]:
        tree = ast.parse(code, filename="<lumlflow eval>", mode="exec")
        namespace = _LazyNamespace(self)
        namespace["__builtins__"] = __builtins__
        stdout = io.StringIO()
        stderr = io.StringIO()
        result: Any = None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                statements = ast.Module(body=tree.body[:-1], type_ignores=[])
                expression = ast.Expression(body=tree.body[-1].value)
                if statements.body:
                    exec(
                        compile(statements, "<lumlflow eval>", "exec"),
                        namespace,
                        namespace,
                    )
                result = eval(
                    compile(expression, "<lumlflow eval>", "eval"),
                    namespace,
                    namespace,
                )
            else:
                exec(
                    compile(tree, "<lumlflow eval>", "exec"),
                    namespace,
                    namespace,
                )
        response: dict[str, object] = {
            "state": "succeeded",
            "result": repr(result),
            "result_type": type(result).__name__,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "touched": self.touched,
        }
        if preview_builder is not None:
            response["preview"] = preview_builder(result)
        return response

    def check_integrity(self, checker: IntegrityChecker) -> None:
        for _name, descriptor in self._touched:
            checker(descriptor)

    def resolve(self, name: str) -> Any:
        if name in self._by_cell:
            return _CellProxy(name, self._by_cell[name], self)
        candidates = self._by_output.get(name)
        if candidates is None:
            raise KeyError(name)
        if len(candidates) > 1:
            choices = ", ".join(candidate for candidate, _descriptor in candidates)
            raise NameError(f"asset name {name!r} is ambiguous; use one of: {choices}")
        qualified_name, descriptor = candidates[0]
        return self.hydrate(qualified_name, descriptor)

    def hydrate(self, qualified_name: str, descriptor: ValueDescriptor) -> Any:
        if qualified_name not in self._touched_names:
            self._touched_names.add(qualified_name)
            self._touched.append((qualified_name, descriptor))
        return self._load_value(descriptor)


class _LazyNamespace(dict[str, Any]):
    def __init__(self, evaluator: ScratchEvaluator) -> None:
        super().__init__()
        self.evaluator = evaluator

    def __missing__(self, name: str) -> Any:
        value = self.evaluator.resolve(name)
        self[name] = value
        return value


class _CellProxy:
    def __init__(
        self,
        slug: str,
        outputs: dict[str, ValueDescriptor],
        evaluator: ScratchEvaluator,
    ) -> None:
        self._slug = slug
        self._outputs = outputs
        self._evaluator = evaluator
        self._values: dict[str, Any] = {}

    def __getattr__(self, output: str) -> Any:
        if output in self._values:
            return self._values[output]
        try:
            descriptor = self._outputs[output]
        except KeyError as error:
            raise AttributeError(
                f"cell {self._slug!r} has no output {output!r}"
            ) from error
        value = self._evaluator.hydrate(f"{self._slug}.{output}", descriptor)
        self._values[output] = value
        return value

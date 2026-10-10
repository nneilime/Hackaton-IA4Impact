"""Pipeline core: steps, flows and the flow registry.

A flow is a class listing step instances. Registering it makes it available by name to the CLI and the API:

    @register_flow
    class MyFlow(Flow):
        name = "my_flow"
        steps = [SomeCleanup(), SomeFilter(), SomeTransform(), SomeCheck()]

Each step reads and mutates a shared Context: the two inputs (facture, bordereau), a scratch dict for
intermediate results, the output record and a list of issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

SEVERITIES = ("info", "warning", "error")


@dataclass
class Issue:
    step: str
    severity: str
    message: str
    field: str | None = None


@dataclass
class Context:
    facture: Any
    bordereau: Any
    assets: dict[str, Any] = field(default_factory=dict)  # trusted side inputs (scan path, cached box OCR...)
    scratch: dict[str, Any] = field(default_factory=dict)
    record: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    failed: bool = False

    def issue(self, step: str, severity: str, message: str, field: str | None = None) -> None:
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        self.issues.append(Issue(step, severity, message, field))

    @property
    def status(self) -> str:
        """The worst severity among the issues: "error", "warning" or "ok"."""
        severities = {i.severity for i in self.issues}
        return "error" if self.failed or "error" in severities else "warning" if "warning" in severities else "ok"


class Step:
    """One unit of work. Subclass Filter, Cleanup, Transform or Validate and implement run()."""

    kind: ClassVar[str] = "step"

    @property
    def name(self) -> str:
        return type(self).__name__

    def run(self, ctx: Context) -> None:
        raise NotImplementedError

    def issue(self, ctx: Context, severity: str, message: str, field: str | None = None) -> None:
        ctx.issue(self.name, severity, message, field)


class Cleanup(Step):
    """Normalises the inputs without dropping anything (encoding, whitespace, coordinates...)."""
    kind = "cleanup"


class Filter(Step):
    """Drops input items that are noise for the later steps."""
    kind = "filter"


class Transform(Step):
    """Builds part of ctx.record from the inputs."""
    kind = "transform"


class Validate(Step):
    """Checks ctx.record and reports issues; never changes the record."""
    kind = "validate"


class Flow:
    name: ClassVar[str]
    description: ClassVar[str] = ""
    steps: ClassVar[list[Step]] = []

    def run(self, facture: Any, bordereau: Any, assets: dict[str, Any] | None = None) -> Context:
        """Run every step in order. A step that raises stops the flow and marks the context as failed.

        assets are inputs the caller vouches for, kept apart from the documents: e.g. "image_path" (the scan) and
        "signature_boxes_ocr" (check_signatures.py's cache). The API never fills them from a request body.
        """
        ctx = Context(facture=facture, bordereau=bordereau, assets=assets or {})
        for step in self.steps:
            try:
                step.run(ctx)
            except Exception as e:
                ctx.issue(step.name, "error", f"step crashed: {type(e).__name__}: {e}")
                ctx.failed = True
                break
        return ctx

    @classmethod
    def describe(cls) -> dict[str, Any]:
        return {"name": cls.name, "description": cls.description,
                "steps": [{"name": s.name, "kind": s.kind} for s in cls.steps]}


_FLOWS: dict[str, type[Flow]] = {}


def register_flow(cls: type[Flow]) -> type[Flow]:
    name = getattr(cls, "name", None)
    if not name:
        raise TypeError(f"{cls.__name__} must define a name")
    if name in _FLOWS and _FLOWS[name] is not cls:
        raise ValueError(f"a flow named {name!r} is already registered")
    if not cls.steps:
        raise TypeError(f"{cls.__name__} has no steps")
    _FLOWS[name] = cls
    return cls


def get_flow(name: str) -> Flow:
    try:
        return _FLOWS[name]()
    except KeyError:
        raise KeyError(f"unknown flow {name!r}, registered: {', '.join(sorted(_FLOWS))}") from None


def registered_flows() -> dict[str, type[Flow]]:
    return dict(_FLOWS)

"""Unsandboxed Python plugin host.

Rationale
---------

Ruyi plugins were originally authored in Starlark and executed through
``xingque`` (a binding to ``starlark-rust``), which provided genuine
language-level isolation. That backend was dropped in October 2024;
see commits ``bc458ce`` (the introduction of this file), ``a9d66bd``
(making it the default), and ``2b7c24d`` / ``9e5abe1`` (removal of the
Starlark backend).

The stated reason in ``bc458ce`` is that the plugin surface was
restricted to standard Python 3 rather than any dialect of it. The
underlying project-level goal is broader: the whole of RuyiSDK is kept
to Python and shell so that onboarding is trivial, so that loss of
project staff is survivable, and so that third-party commercial
partners can take over maintenance of their own forks without being
blocked by any non-trivial piece of code in a less widely known
language. Reintroducing Starlark -- or any other embedded language or
Rust-backed sandbox -- would reintroduce exactly the kind of
specialist-knowledge cliff this policy exists to avoid, and is
therefore not on the table regardless of its technical merits.

Threat model and non-goals
--------------------------

This module is intentionally *not* a sandbox. Plugin sources are
parsed, AST-linted, compiled, and ``exec``-ed in the host interpreter
with a curated ``__builtins__`` mapping. A malicious plugin can escape
trivially.

The original justification, as recorded in ``bc458ce`` in 2024, was:

    No "outsiders" are involved in plugin creation yet, and attacks
    from "insiders" are not going to be thwarted by code-level
    sandboxing alone.

That premise has since lapsed and the quote should be read as
historical rather than current. Third-party addon repositories are a
supported feature, which means plugin code loaded by Ruyi can now
originate from authors outside the project. An unsandboxed Python
runtime provides no meaningful defence against a hostile or
compromised third-party addon; in particular, the capability set in
``PluginHostContext`` (``call-subprocess-v1``, ``build-recipe-v1``,
``i18n-v1``, ...) is an API-shape boundary, not a security boundary,
and is trivially escapable from in-process Python.

The present mitigations against this are operational rather than
technical: a prominent warning and explicit user confirmation on
``ruyi repo add``, and the expectation that users extend trust to
third-party repos on the same footing as any other third-party code
they choose to run. Revisiting this with an actual sandbox (process
isolation, a reintroduced Starlark backend, or another mechanism) is
out of scope of this module and currently gated on project-level
decisions rather than technical ones; see
https://github.com/ruyisdk/ruyi/issues/444 for tracking.

Recursion detection, resource limits, timeouts, and filesystem or
network isolation are likewise out of scope here; they are not
soundly achievable with pure AST inspection plus ``exec`` in CPython.

What the module does enforce, and why, is documented on the
individual enforcement points themselves: ``BUILTINS_TO_EXPOSE``,
``GatedLanguageFeaturesPass``, and ``_load_stmt_helper`` below, plus
the ``PluginHostContext`` capability set in ``api.py`` /
``build_api.py``. The unifying goal of those checks is not security
but *Starlark portability*: keeping plugin sources close to the shape
of the original Starlark subset so that a future move back to a real
Starlark runtime -- should the project-level policy above ever shift
-- would not require rewriting every in-tree plugin.
"""

import ast
import builtins
import inspect
import os
import pathlib
from types import CodeType
from typing import Callable, Final, MutableMapping, NoReturn, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Buffer

from .api import RuyiHostAPI
from .ctx import PluginHostContext, BasePluginLoader, PluginLoadMode


class UnsandboxedModuleDict(dict[str, object]):
    def get_option(self, key: str) -> object:
        return self.get(key, None)


class UnsandboxedTrivialEvaluator:
    def eval_function(
        self,
        function: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        if callable(function):
            return function(*args, **kwargs)
        raise RuntimeError(f"the Python value {function!r} is not callable")


# The set of Python builtins exposed to plugin code in place of the real
# ``builtins`` module. Membership criterion: the name must either exist in
# Starlark or map cleanly onto a Starlark equivalent, so that keeping a
# plugin portable to a future Starlark backend does not require giving up
# any builtin listed here. Introspection / reflection / dynamic-eval
# builtins (``eval``, ``exec``, ``compile``, ``globals``, ``locals``,
# ``vars``, ``__import__``, ``open``, ...) are deliberately absent for the
# same reason: they have no Starlark counterpart. This is a portability
# fence, not a security boundary -- see the module docstring.
BUILTINS_TO_EXPOSE: Final = {
    k: getattr(builtins, k)
    for k in [
        "abs",
        "any",
        "all",
        "bool",
        "bytes",
        "dict",
        "dir",
        "enumerate",
        "float",
        "getattr",
        "hasattr",
        "hash",
        "int",
        "len",
        "list",
        "max",
        "min",
        "print",
        "range",
        "repr",
        "reversed",
        "sorted",
        "str",
        "tuple",
        "type",
        "zip",
    ]
}


def _fail_helper(*args: object) -> NoReturn:
    raise RuntimeError(f"fail: {''.join(str(x) for x in args)}")


class UnsandboxedPluginHostContext(
    PluginHostContext[UnsandboxedModuleDict, UnsandboxedTrivialEvaluator]
):
    def make_loader(
        self,
        originating_file: pathlib.Path,
        module_cache: MutableMapping[str, UnsandboxedModuleDict],
        load_mode: PluginLoadMode,
    ) -> BasePluginLoader[UnsandboxedModuleDict]:
        return UnsandboxedRuyiPluginLoader(
            self, originating_file, module_cache, load_mode
        )

    def make_evaluator(self) -> UnsandboxedTrivialEvaluator:
        return UnsandboxedTrivialEvaluator()


def _is_name_private(n: str) -> bool:
    return n.startswith("_")


def _assert_name_is_public(n: str) -> None | NoReturn:
    if _is_name_private(n):
        raise RuntimeError(f"error: trying to load private name {n}")
    return None


class UnsandboxedRuyiPluginLoader(BasePluginLoader[UnsandboxedModuleDict]):
    def do_load_module(
        self,
        resolved_path: pathlib.Path,
        program: str,
        ruyi_host_bridge: Callable[[object], RuyiHostAPI],
    ) -> UnsandboxedModuleDict:
        self.host_logger.D(f"unsandboxed module load: path {resolved_path}")

        sub_loader = self.make_sub_loader(resolved_path)

        def _load_stmt_helper(
            spec: str,
            *values_to_bind: str,
            **renamed_values_to_bind: str,
        ) -> None:
            """Starlark-style ``load()`` exposed to plugins.

            This is deliberately *not* a wrapper over Python ``import``:
            it mirrors Starlark's ``load()`` statement so that plugin
            sources remain portable to a real Starlark backend. In
            particular, it binds names by injection into the caller's
            frame (matching Starlark semantics), and it refuses to bind
            names beginning with ``_``, matching Starlark's rule that
            underscore-prefixed symbols are module-private.

            ``import`` / ``from ... import ...`` are separately rejected
            by ``GatedLanguageFeaturesPass`` so that ``load()`` is the
            only way for plugins to pull in other modules.
            """
            mod = sub_loader.load(spec)

            curr_frame = inspect.currentframe()
            if curr_frame is None:
                raise RuntimeError(
                    "cannot inspect the Python runtime for the current frame"
                )

            parent_frame = curr_frame.f_back
            if parent_frame is None:
                raise RuntimeError(
                    "internal error: no parent frame for load() statement"
                )

            g = parent_frame.f_locals
            for name in values_to_bind:
                _assert_name_is_public(name)
                g[name] = mod[name]
            for dst_name, src_name in renamed_values_to_bind.items():
                _assert_name_is_public(src_name)
                g[dst_name] = mod[src_name]
            return None

        code = self.source_to_code(program, resolved_path)
        mod_globals: dict[str, object] = {
            "__builtins__": BUILTINS_TO_EXPOSE,
            "fail": _fail_helper,
            "load": _load_stmt_helper,
            "ruyi_plugin_rev": ruyi_host_bridge,
        }
        # pylint: disable-next=exec-used
        exec(code, mod_globals)
        return UnsandboxedModuleDict(mod_globals)

    # intentionally follows the importlib.abc.InspectLoader protocol, for
    # easier refactoring whenever necessary.
    @staticmethod
    def source_to_code(
        data: "Buffer | str | ast.Module",
        path: "str | os.PathLike[str]" = "<string>",
    ) -> CodeType:
        mod_ast: ast.Module
        if isinstance(data, ast.Module):
            mod_ast = data
        else:  # isinstance(data, str) or isinstance(data, Buffer)
            mod_ast = ast.parse(data, path, "exec")

        # lint the module on a best-effort basis to help fight syntax feature
        # creep
        lint_module(mod_ast)

        return compile(mod_ast, path, "exec")


def lint_module(mod: ast.Module) -> None:
    """Run best-effort parse-time lints over a plugin module AST.

    Currently this runs only ``GatedLanguageFeaturesPass``; additional
    best-effort static checks (for example a call-graph pass flagging
    obvious direct or mutual recursion) may be layered in over time.
    Anything added here should be understood as a lint, not a soundness
    guarantee -- see the module docstring for why real enforcement is
    out of scope.
    """
    try:
        GatedLanguageFeaturesPass().visit(mod)
    except _GatedFeatureError as e:
        raise RuntimeError(
            f"line {e.node.lineno}: {e.feature} is not allowed in plugin code"
        ) from e


class _GatedFeatureError(Exception):
    """Internal signal raised by ``GatedLanguageFeaturesPass`` when it
    encounters a gated construct. Carries the offending AST node (for
    its line number) and a short human-readable name of the feature,
    so ``lint_module`` can surface a useful diagnostic instead of the
    bare node type.
    """

    def __init__(self, node: ast.stmt | ast.expr, feature: str) -> None:
        super().__init__(feature)
        self.node = node
        self.feature = feature


def _reject_annotated_args(args: ast.arguments) -> None:
    """Raise ``_GatedFeatureError`` if any parameter in ``args`` carries
    a type annotation. Starlark's Parameter grammar has no annotation
    production, so annotations on any category of parameter -- regular,
    positional-only, keyword-only, ``*args``, or ``**kwargs`` -- are
    rejected uniformly.
    """
    for arg in (
        *args.posonlyargs,
        *args.args,
        *args.kwonlyargs,
        *((args.vararg,) if args.vararg is not None else ()),
        *((args.kwarg,) if args.kwarg is not None else ()),
    ):
        if arg.annotation is not None:
            raise _GatedFeatureError(arg.annotation, "parameter type annotation")


class GatedLanguageFeaturesPass(ast.NodeVisitor):
    """Reject Python syntax that has no Starlark analogue.

    Each ``visit_*`` override below names one construct that is gated
    at parse time. The selection criterion is *Starlark portability*,
    not safety: a feature is gated if accepting it would make it
    materially harder to move plugin sources back to a real Starlark
    runtime later. Rejected constructs include, among others:

    * ``NamedExpr`` (walrus) -- not in Starlark.
    * ``Raise``, ``Assert`` -- Starlark uses ``fail()`` for errors.
    * ``Import`` / ``ImportFrom`` -- Starlark uses ``load()``; see
      ``_load_stmt_helper``.
    * ``Try`` / ``TryStar`` / ``With`` -- no Starlark equivalents.
    * ``Match`` -- not in Starlark.
    * ``Yield`` / ``YieldFrom`` -- Starlark has no generators.
    * ``Global`` / ``Nonlocal`` -- Starlark's scoping rules differ.
    * ``ClassDef`` -- Starlark has no user-defined classes.
    * ``AsyncFunctionDef`` / ``Await`` / ``AsyncFor`` / ``AsyncWith``
      -- Starlark has no async model.

    The gate is necessarily best-effort: CPython's grammar is larger
    than Starlark's and evolves between releases. When a new language
    feature lands in CPython, the default choice should be to add it
    here -- anything not already required by an existing plugin is
    cheaper to forbid now than to un-ship later.

    This is a portability fence, not a security boundary; see the
    module docstring.
    """

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        raise _GatedFeatureError(node, "walrus operator (`:=`)")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Decorators have no analogue in the Starlark ``DefStmt`` grammar.
        # Reject them, but continue recursing into the body so that other
        # gated constructs inside the function are still reported.
        if node.decorator_list:
            raise _GatedFeatureError(node.decorator_list[0], "decorator")
        # Starlark's parameter grammar has no annotation syntax, and its
        # function headers have no return-type annotation. Reject both.
        if node.returns is not None:
            raise _GatedFeatureError(node.returns, "return type annotation")
        _reject_annotated_args(node.args)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        raise _GatedFeatureError(node, "variable type annotation")

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # Starlark's lexical grammar offers only plain string and bytes
        # literals. Reject f-strings so that plugin sources stay portable.
        raise _GatedFeatureError(node, "f-string")

    def visit_Raise(self, node: ast.Raise) -> None:
        raise _GatedFeatureError(node, "`raise` statement")

    def visit_Assert(self, node: ast.Assert) -> None:
        raise _GatedFeatureError(node, "`assert` statement")

    def visit_Import(self, node: ast.Import) -> None:
        raise _GatedFeatureError(node, "`import` statement")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise _GatedFeatureError(node, "`from ... import ...` statement")

    def visit_Try(self, node: ast.Try) -> None:
        raise _GatedFeatureError(node, "`try` statement")

    def visit_TryStar(self, node: ast.TryStar) -> None:
        raise _GatedFeatureError(node, "`try ... except*` statement")

    def visit_With(self, node: ast.With) -> None:
        raise _GatedFeatureError(node, "`with` statement")

    def visit_Match(self, node: ast.Match) -> None:
        raise _GatedFeatureError(node, "`match` statement")

    def visit_Yield(self, node: ast.Yield) -> None:
        raise _GatedFeatureError(node, "`yield` expression")

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        raise _GatedFeatureError(node, "`yield from` expression")

    def visit_Global(self, node: ast.Global) -> None:
        raise _GatedFeatureError(node, "`global` statement")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise _GatedFeatureError(node, "`nonlocal` statement")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        raise _GatedFeatureError(node, "`class` definition")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        raise _GatedFeatureError(node, "`async def` function")

    def visit_Await(self, node: ast.Await) -> None:
        raise _GatedFeatureError(node, "`await` expression")

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        raise _GatedFeatureError(node, "`async for` loop")

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        raise _GatedFeatureError(node, "`async with` statement")

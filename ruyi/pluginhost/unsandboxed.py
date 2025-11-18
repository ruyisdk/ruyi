import ast
import builtins
import inspect
import os
import pathlib
import sys
from types import CodeType
from typing import Callable, Final, MutableMapping, NoReturn, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing_extensions import Buffer

from .api import RuyiHostAPI
from .ctx import PluginHostContext, BasePluginLoader


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
        is_cmd: bool,
    ) -> BasePluginLoader[UnsandboxedModuleDict]:
        return UnsandboxedRuyiPluginLoader(self, originating_file, module_cache, is_cmd)

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
    if node := GatedLanguageFeaturesPass().visit(mod):
        raise RuntimeError(f"line {node.lineno}: language feature is gated")


class GatedLanguageFeaturesPass(ast.NodeVisitor):
    def visit(self, node: ast.AST) -> ast.expr | ast.stmt | None:
        return cast(ast.expr | ast.stmt | None, super().visit(node))

    def generic_visit(self, node: ast.AST) -> ast.expr | ast.stmt | None:
        """Traverses all types of nodes, bailing if non-minimal language
        features are found."""

        for _, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        if x := self.visit(item):
                            return x
            elif isinstance(value, ast.AST):
                if x := self.visit(value):
                    return x
        return None

    def visit_NamedExpr(self, node: ast.NamedExpr) -> ast.NamedExpr:
        return node

    def visit_Raise(self, node: ast.Raise) -> ast.Raise:
        return node

    def visit_Assert(self, node: ast.Assert) -> ast.Assert:
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        return node

    def visit_Try(self, node: ast.Try) -> ast.Try:
        return node

    if sys.version_info >= (3, 11):

        def visit_TryStar(self, node: ast.TryStar) -> ast.TryStar:
            return node

    def visit_With(self, node: ast.With) -> ast.With:
        return node

    def visit_Match(self, node: ast.Match) -> ast.Match:
        return node

    def visit_Yield(self, node: ast.Yield) -> ast.Yield:
        return node

    def visit_YieldFrom(self, node: ast.YieldFrom) -> ast.YieldFrom:
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.Nonlocal:
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        return node

    def visit_Await(self, node: ast.Await) -> ast.Await:
        return node

    def visit_AsyncFor(self, node: ast.AsyncFor) -> ast.AsyncFor:
        return node

    def visit_AsyncWith(self, node: ast.AsyncWith) -> ast.AsyncWith:
        return node

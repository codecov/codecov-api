# async_orm_checker.py

from mypy.nodes import CallExpr, FuncDef, MemberExpr
from mypy.plugin import FunctionContext, Plugin
from mypy.traverser import TraverserVisitor
from mypy.types import Instance

# ORM method names that should not be used in async functions
SYNC_ORM_METHODS = {"get", "filter", "create", "update", "delete"}


class SyncORMInAsyncChecker(TraverserVisitor):
    def __init__(self, plugin, ctx: FunctionContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx

    def visit_call_expr(self, expr: CallExpr):
        # Check if the function call is accessing an ORM method
        if isinstance(expr.callee, MemberExpr):
            method_name = expr.callee.name
            if method_name in SYNC_ORM_METHODS:
                # Check if this is a method on a Django model instance
                if isinstance(expr.callee.expr, Instance):
                    if (
                        "django.db.models.base.Model"
                        in expr.callee.expr.type.type.fullname
                    ):
                        # Trigger an error if a sync ORM method is used in an async context
                        self.plugin.fail(
                            f"Sync ORM method '{method_name}' used in async function; wrap in sync_to_async",
                            expr,
                        )
        super().visit_call_expr(expr)


class AsyncORMPlugin(Plugin):
    def get_function_hook(self, fullname: str):
        # Only run this check on async functions
        def wrapper(ctx: FunctionContext):
            func_def = ctx.context
            if isinstance(func_def, FuncDef) and func_def.is_async:
                # Traverse the async function to look for sync ORM calls
                checker = SyncORMInAsyncChecker(self, ctx)
                func_def.accept(checker)
            return ctx.default_return_type

        return wrapper


def plugin(version: str):
    return AsyncORMPlugin

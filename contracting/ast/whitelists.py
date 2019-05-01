import ast

ALLOWED_AST_TYPES = {
    ast.Add,
    ast.And,
    ast.arg,
    ast.arguments,
    ast.Assert,
    ast.Assign,
    ast.Attribute,
    ast.AugAssign,
    ast.BinOp,
    ast.BoolOp,
    ast.Call,
    ast.Compare,
    ast.comprehension,
    ast.Dict,
    ast.Div,
    ast.Eq,
    ast.Expr,
    ast.For,
    ast.FunctionDef,
    ast.Gt,
    ast.GtE,
    ast.If,
    ast.Import,
    ast.In,
    ast.Index,
    ast.keyword,
    ast.List,
    ast.ListComp,
    ast.Load,
    ast.Lt,
    ast.LtE,
    ast.Mod,
    ast.Module,
    ast.Mult,
    ast.Name,
    ast.NameConstant,
    ast.Not,
    ast.NotEq,
    ast.NotIn,
    ast.Num,
    ast.Or,
    ast.Pass,
    ast.Pow,
    ast.Return,
    ast.Set,
    ast.Slice,
    ast.Starred,
    ast.Store,
    ast.Str,
    ast.Sub,
    ast.Subscript,
    ast.Tuple,
    ast.UnaryOp,
    ast.USub,
    ast.While,
}

VIOLATION_TRIGGERS = [
    "S1- Illegal contracting syntax type used",
    "S2- Illicit use of '_' before variable",
    "S3- Illicit use of Nested imports",
    "S4- ImportFrom ast nodes not yet supported",
    "S5- Contract not found in lib",
    "S6- Illicit use of classes",
    "S7- Illicit use of Async functions",
    "S8- Invalid decorator used",
    "S9- Multiple use of constructors detected",
    "S10- Illicit use of multiple decorators",
    "S11- Illicit keyword overloading for ORM assignments",
    "S12- Multiple targets to ORM definition detected",
    "S13- No valid contracting decorator found"
]

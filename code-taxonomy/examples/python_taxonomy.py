from code_taxonomy import Search


class PythonSearch(Search):
    globs = {"*.py"}


class ClassDeclaration(PythonSearch):
    epic = "Class declaration"

    pattern = r"class {classname}(?:\({class_parents}\))?:"
    classname = r"[a-zA-Z_]\w*"
    class_parents = r"[^)]*"


class FunctionDeclaration(PythonSearch):
    epic = "Function declaration"

    pattern = r"def {function_name}\({function_args}\):"
    function_name = r"[a-zA-Z_]\w*"
    function_args = r"[^)]*"


if __name__ == "__main__":
    PythonSearch.main()

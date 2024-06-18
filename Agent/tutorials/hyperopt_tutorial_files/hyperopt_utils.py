import ast
import re
from typing import Any, Dict, List, Tuple, Union


def convert_to_single_line_blocks(code: str) -> List[str]:
    """Remove multi-line expressions from code and outputs list of single-line expressions.

    Args:
        code: string containing the code to convert

    Returns:
        blocks: list of single-line expressions
    """
    blocks = []
    code = code.split("\n")
    i = 0
    new_block = ""
    n_diff = 0
    while i < len(code):
        #         comment_ind = code[i].find("#") --> we should exclude the comments from the count...
        n_diff += code[i][:].count("(") - code[i].count(")")
        assert n_diff >= 0, (n_diff, code[i])
        new_block += re.sub(
            r'(\s([?,.!"]))|(?<=\[|\()(.*?)(?=\)|\])', lambda x: x.group().strip(), code[i]
        )  # remove space in parentheses
        if n_diff == 0:
            blocks.append(new_block)
            new_block = ""
            n_diff = 0
        i += 1
    assert n_diff == 0
    return blocks


def find_matching_parenthesis(line: str, start_ind: int, parenthesis_type: str, matching: str = None) -> int:
    """Returns the index of the closing parenthesis matching the opening parenthesis at index
    `start_ind`"""
    assert line[start_ind] == parenthesis_type
    if matching is None:
        parenthesis_pairs = ["()", "{}", "[]", "''", '""']
        matching = {p[0]: p[1] for p in parenthesis_pairs}[parenthesis_type]
    n_open = 1
    for i in range(start_ind + 1, len(line)):
        if line[i] == parenthesis_type:
            n_open += 1
        elif line[i] == matching:
            n_open -= 1
            if n_open == 0:
                return i
    raise IndexError(f"No matching opening parens at: {start_ind}")


def parse_function_call(func_call_str: str) -> List[Union[Tuple[str, str], str]]:
    """Extract positional arguments and kw argumens from a string corresponding to a function call.

    Args:
        func_call_str: string corresponding to a function call

    Example:
        >>> func_call = "f(x, asda, c={'as': '12'}, a=[1, 2], b='asd=,wd')"
        >>> print(parse_function_call(func_call))
    """
    tree = ast.parse(func_call_str)

    # The function call is the first element of the body
    func_call_node = tree.body[0].value

    # Fetch positional arguments names
    arg_list = [arg.id for arg in func_call_node.args]

    # The keywords are in the keywords attribute of the function call node
    keyword_list = [(keyword.arg, ast.literal_eval(keyword.value)) for keyword in func_call_node.keywords]

    return arg_list + keyword_list


def transform_args(args: List[Union[Tuple[str, str], str]], map_args: Dict[str, Any]) -> str:
    """Get string of argument assignment.

    Args:
        args: list of positional (str) / kw arguments (tuple of 2 strings)
        map_args: dictionary to map kw arguments

    Example:
        >>> func_call = "f(x, asda, c={'as': '12'}, a=[1, 2], b='asd=,wd')"
        >>> print(parse_function_call(func_call))
    """
    output = ""
    seen_args = set()

    def parse_arg(arg_: str) -> str:
        if not isinstance(arg_, str):
            return arg_
        return f"'{arg_}'"

    for arg in args:
        if not isinstance(arg, tuple):
            output += arg + ", "
        else:
            k = arg[0]
            if k not in map_args:
                output += f"{k}={parse_arg(arg[1])}, "
            else:
                seen_args.add(k)
                output += f"{k}={parse_arg(map_args[k])}, "

    for arg, arg_val in map_args.items():
        if arg in seen_args:
            continue
        output += f"{arg}={parse_arg(arg_val)}, "

    if output[-2:] == ", ":
        output = output[:-2]
    return output


def assign_hyperopt(code: str, space: Dict[str, Dict[str, Any]]) -> str:
    """Modify a code to add hyperparameters.

    Args:
        code: original code without hyperparameters names
        space: dictionary corresponding to the hyperparameter space

    Returns:
        blackbox_code: wrapped input `code` to make it a function of hyperparameters specified in the given `space`
    """
    blackbox_code = ""
    # arguments = {function: {param: f"{function.lower()}__{param}" for param in space[function]} for function in space}
    arguments = {function: {param: space[function][param] for param in space[function]} for function in space}

    blocks = convert_to_single_line_blocks(code)

    for line in blocks:
        for function in space:
            pattern = f"{function}("
            ind = line.find(pattern)
            if ind != -1:
                end_ind = find_matching_parenthesis(line=line, start_ind=ind + len(pattern) - 1, parenthesis_type="(")
                args = parse_function_call(line[ind: end_ind + 1])

                line = line[:ind] + pattern + transform_args(args, arguments[function]) + line[end_ind:]
        blackbox_code += line + "\n"
    return blackbox_code
from src.trmeric_services.tango.functions.library.index import FUNCTIONS


def listFunctions():
    compiled_list = ""
    for function in FUNCTIONS:
        compiled_list += function.format_function() + "\n\n"
    return compiled_list

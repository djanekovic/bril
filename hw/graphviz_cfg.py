def generate_graphviz_code(cfg, function_name):
    def generate_graphviz_vertices():
        return "\n".join([f"  {key};" for key in cfg.keys()])

    def generate_graphviz_edges():
        return "\n".join([f"  {key} -> {value};" for key, values in cfg.items() for value in values])

    return f"""
digraph {function_name} {{
{generate_graphviz_vertices()}
{generate_graphviz_edges()}
}}
    """


def get_graphviz_cfg():
    prog = json.load(sys.stdin)

    for function in prog["functions"]:
        cfg = CFG(function)
        graphviz_code = generate_graphviz_code(cfg.cfg, cfg.function_name)
        print (graphviz_code)


if __name__ == "__main__":
    get_graphviz_cfg()

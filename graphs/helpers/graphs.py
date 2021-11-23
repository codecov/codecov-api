from operator import itemgetter

from graphs.settings import settings

from .graph_utils import (
    _layout,
    _make_svg,
    _max_aspect_ratio,
    _squarify,
    _svg_polar_rect,
    _svg_rect,
    _tree_height,
    _worst_ratio,
)


def tree(parsed_data, href=None, classes=None, **kwargs):
    """
    [
        {
            "lines": 10,
            "color": "#aaaeee",
            "children": [],
            "name": "path"
        }
    ]
    """
    options = settings["sunburst"]["options"].copy()
    options.update(kwargs)

    svg_elements = []

    def recursively_draw(items, step, left, top, width, height):
        values = [item["lines"] for item in items]
        _sum_values = sum(values)
        if _sum_values > 0:
            correction = width * height / _sum_values
            sorted_values = sorted(
                enumerate(value * correction for value in values),
                key=itemgetter(1),
                reverse=True,
            )
            indices = [x[0] for x in sorted_values]
            values = [x[1] for x in sorted_values]
            rectangles = _squarify(values, left, top, width, height)
            for rect, color, _class, children, name in zip(
                rectangles,
                (items[index]["color"] for index in indices),
                (items[index]["_class"] for index in indices),
                (items[index].get("children", None) for index in indices),
                (items[index]["name"] for index in indices),
            ):
                step.append(name)
                if children:
                    recursively_draw(children, step, *rect)
                    step.pop(-1)
                else:
                    path = "/".join(step[1:])
                    rect = _svg_rect(
                        rect[0],
                        rect[1],
                        rect[2],
                        rect[3],
                        fill=color,
                        stroke=options["border_color"],
                        stroke_width=options["border_size"],
                        _class=_class,
                        title=path,
                    )
                    svg_elements.append(rect)
                    step.pop(-1)

    recursively_draw(
        parsed_data,
        [],
        0,
        0,
        options.get("viewPortWidth") or options["width"],
        options.get("viewPortHeight") or options["height"],
    )

    return _make_svg(
        options["width"],
        options["height"],
        svg_elements,
        options.get("viewPortWidth"),
        options.get("viewPortHeight"),
    )


def icicle(parsed_data, **kwargs):
    options = settings["icicle"]["options"].copy()
    options.update(kwargs)

    drawing_width = options["width"]
    drawing_height = options["height"]

    # ensure 5% frame
    plot_width = drawing_width * 0.9
    plot_height = drawing_height * 0.9

    # starting point
    sx, sy = drawing_width * 0.05, drawing_height * 0.05
    strip_height = plot_height / _tree_height(parsed_data)

    svg_elements = []

    def recursively_draw(items, x, y, max_width, prefix_name):
        total = sum((item["lines"] for item in items))
        if total > 0:
            for item in items:
                item_width = item["lines"] / total * max_width
                title = prefix_name + "/" + item["name"]
                svg_elements.append(
                    _svg_rect(
                        x,
                        y,
                        item_width,
                        strip_height,
                        fill=item["color"],
                        stroke=options["border_color"],
                        title=title,
                        stroke_width=options["border_size"],
                    )
                )
                if "children" in item.keys():
                    recursively_draw(
                        item["children"], x, y + strip_height, item_width, title
                    )
                x += item_width

    recursively_draw(parsed_data, sx, sy, plot_width, "")

    return _make_svg(drawing_width, drawing_height, svg_elements)


def sunburst(parsed_data, **kwargs):
    options = settings["sunburst"]["options"].copy()
    options.update(kwargs)

    drawing_width = options["width"]
    drawing_height = options["height"]
    cx = drawing_width / 2.0
    cy = drawing_height / 2.0

    # ensure 5% frame
    max_diameter = min(drawing_width, drawing_height) * 0.95
    max_radius = max_diameter / 2.0

    offset_increment = max_radius / _tree_height(parsed_data)

    svg_elements = []

    def recursively_draw(items, inner_radius, start, end):
        total = sum((item["lines"] for item in items))
        if total > 0:
            s = start
            for item in items:
                arc_size = item["lines"] / total * (end - start)
                svg_elements.append(
                    _svg_polar_rect(
                        cx,
                        cy,
                        inner_radius,
                        inner_radius + offset_increment,
                        s,
                        s + arc_size,
                        item["color"],
                        options["border_color"],
                        options["border_size"],
                    )
                )
                if "children" in item.keys():
                    recursively_draw(
                        item["children"],
                        inner_radius + offset_increment,
                        s,
                        s + arc_size,
                    )
                s += arc_size

    recursively_draw(parsed_data, 0, 0, 1)

    return _make_svg(drawing_width, drawing_height, svg_elements)

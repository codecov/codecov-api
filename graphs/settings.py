settings = {
    "icicle": {
        "method": "flare",
        "options": {
            "width": 750,
            "height": 150,
            "border_size": 1,
            "border_color": "white",
        },
        "exports": ["svg"],
        "types": ["commit", "pull", "branch"],
    },
    "tree": {
        "method": "flare",
        "options": {
            "width": 500,
            "height": 500,
            "border_size": 1,
            "border_color": "white",
        },
        "exports": ["svg", "json"],
        "types": ["commit", "pull", "branch"],
    },
    "sunburst": {
        "method": "flare",
        "options": {
            "width": 300,
            "height": 300,
            "border_size": 1,
            "border_color": "white",
        },
        "exports": ["svg", "html"],
        "types": ["commit", "pull", "branch"],
    },
    "commits": {
        "method": "commits",
        "options": {
            "width": 700,
            "height": 100,
            "color": "yes",
            "legend": "yes",
            "yaxis": [0, 100],
            "hg": "yes",
            "vg": "yes",
            "limit": 20,
        },
        "exports": ["svg", "json"],
        "types": ["pull", "branch"],
    },
}

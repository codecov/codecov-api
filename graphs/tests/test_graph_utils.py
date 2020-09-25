from graphs.helpers.graph_utils import _tree_height


class TestGraphsUtils(object):

    def test_tree_height(self):

        tree = [
            {
                "name": "name_0",
            }
        ]

        height = _tree_height(tree)
        assert height == 1

        tree = [
            {
                "name": "name_0",
                "children": [
                    {
                        "name": "name_2"
                    }
                ]
            }
        ]
        
        height = _tree_height(tree)
        assert height == 2

        tree = [
            {
                "name": "name_0",
                "children": [
                    {
                        "name": "name_1",
                        "children": [
                            {
                                "name": "name_2"
                            }
                        ]
                    },
                    {
                        "name": "name_3"
                    }
                ]
            }
        ]
        height = _tree_height(tree)
        assert height == 3

        tree = [
            {
                "name": "name_0",
                "children": [
                    {
                        "name": "name_1",
                        "children": [
                            {
                                "name": "name_2",
                                "children": [
                                    {
                                        "name": "name_4"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "name": "name_3"
                    }
                ]
            }
        ]
        height = _tree_height(tree)
        assert height == 4

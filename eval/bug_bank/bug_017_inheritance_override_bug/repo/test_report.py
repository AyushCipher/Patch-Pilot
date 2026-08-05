from shapes import Rectangle, Triangle
from report import total_area


def test_total_area_mixed_shapes():
    shapes = [Rectangle(4, 5), Triangle(6, 4)]
    assert total_area(shapes) == 32.0


def test_triangle_area_alone():
    assert Triangle(10, 3).area() == 15.0

def total_area(shapes: list) -> float:
    """Sum the area of a mixed list of Shape subclasses."""
    return sum(s.area() for s in shapes)

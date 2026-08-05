class Shape:
    """Base contract: area() must return the true geometric area of the
    shape. Subclasses must preserve this invariant - callers aggregate
    areas polymorphically and never special-case a particular subclass."""

    def area(self) -> float:
        raise NotImplementedError

    def describe(self) -> str:
        return f"area={self.area():.2f}"


class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height


class Triangle(Shape):
    def __init__(self, base: float, height: float):
        self.base = base
        self.height = height

    def area(self) -> float:
        return self.base * self.height

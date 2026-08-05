class User:
    def __init__(self, user_id, email, is_active=True):
        self.user_id = user_id
        self.email = email
        self.is_active = is_active

    def to_dict(self) -> dict:
        return {"id": self.user_id, "email": self.email, "active": self.is_active}

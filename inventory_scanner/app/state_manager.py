class AppState:
    current_user = None
    user_id = None
    is_admin = False
    is_logged_in = False

    @classmethod
    def login(cls, username, user_id=None, is_admin=False):
        cls.current_user = username
        cls.user_id = user_id
        cls.is_admin = is_admin
        cls.is_logged_in = True

    @classmethod
    def logout(cls):
        cls.current_user = None
        cls.user_id = None
        cls.is_admin = False
        cls.is_logged_in = False

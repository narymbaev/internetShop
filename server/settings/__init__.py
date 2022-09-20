from settings import local

_settings_instance = None


class Settings:
    class PostgreSQL:

        def __init__(self):
            self.database = local.settings['psql']['database']
            self.host = local.settings['psql']['host']
            self.port = local.settings['psql']['port']
            self.user = local.settings['psql']['user']
            self.password = local.settings['psql']['password']

    def __init__(self):
        self.psql = Settings.PostgreSQL()

    @classmethod
    def instance(cls):
        global _settings_instance
        if not _settings_instance:
            _settings_instance = cls()
        return _settings_instance

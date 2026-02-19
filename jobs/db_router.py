"""
Database router for genzjobs shared PostgreSQL database.

Routes GenzjobsListing model reads/writes to the 'genzjobs' database.
All other models use the default database.
"""


class GenzjobsRouter:
    """
    Router that directs GenzjobsListing operations to the genzjobs database.
    """

    GENZJOBS_MODELS = {'genzjobslisting'}

    def db_for_read(self, model, **hints):
        if model._meta.model_name in self.GENZJOBS_MODELS:
            return 'genzjobs'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.model_name in self.GENZJOBS_MODELS:
            return 'genzjobs'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Never allow cross-database relations
        db1 = self._get_db(obj1)
        db2 = self._get_db(obj2)
        if db1 and db2:
            return db1 == db2
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never migrate anything on genzjobs (managed externally by Prisma)
        if db == 'genzjobs':
            return False
        # Don't migrate genzjobs models on default DB
        if model_name in self.GENZJOBS_MODELS:
            return False
        return None

    def _get_db(self, obj):
        if obj._meta.model_name in self.GENZJOBS_MODELS:
            return 'genzjobs'
        return 'default'

from store import PICKEM_SCHEMA, SupabaseStore


class FakeSchemaClient:
    def __init__(self):
        self.schemas = []
        self.tables = []

    def schema(self, name):
        self.schemas.append(name)
        return self

    def table(self, name):
        self.tables.append(name)
        return (name, self.schemas[-1])


def test_store_uses_explicit_pickem_schema_per_query():
    store = SupabaseStore.__new__(SupabaseStore)
    fake = FakeSchemaClient()
    store.client = fake

    result = store._table("players")

    assert result == ("players", PICKEM_SCHEMA)
    assert fake.schemas == ["pickem"]
    assert fake.tables == ["players"]

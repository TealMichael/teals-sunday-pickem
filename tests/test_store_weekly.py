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


def test_all_gate2_tables_still_route_explicitly_to_pickem_schema():
    store = SupabaseStore.__new__(SupabaseStore)
    fake = FakeSchemaClient()
    store.client = fake
    for name in ["weeks", "player_pool", "lineups", "lineup_picks"]:
        assert store._table(name) == (name, PICKEM_SCHEMA)
    assert fake.schemas == [PICKEM_SCHEMA] * 4

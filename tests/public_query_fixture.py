"""Model only the explicit public projection, not a PostgreSQL server."""
PROFILE_FIELDS = "id,nickname,emoji"

def project(rows, fields, tables):
    """Fixture-only projection of the explicitly supported nested read shape.

    This models documented PostgREST left-join JSON; it is not PostgreSQL.
    """
    if fields == "*":
        return rows
    if ",players(" in fields and "lineup_picks(" not in fields:
        result = []
        for item in rows:
            value = {k:item.get(k) for k in fields.split(",players(",1)[0].split(",")}
            person = next((p for p in tables["players"] if p["id"] == item["player_id"]), None)
            value["players"] = {k:person.get(k) for k in PROFILE_FIELDS.split(",")} if person else None
            result.append(value)
        return result
    return [{key: row.get(key) for key in fields.split(",")} for row in rows]

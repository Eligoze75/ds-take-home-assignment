from dataclasses import dataclass
import duckdb


@dataclass
class ItemSearchIndex:
    categories: list[str]
    manufacturers: list[str]
    sku_lookup: dict[str, dict]
    items_by_category: dict[str, list[str]]
    items_by_manufacturer: dict[str, list[str]]
    items_by_manufacturer_id: dict[str, list[str]]


def build_index(con: duckdb.DuckDBPyConnection) -> ItemSearchIndex:
    categories = (
        con.sql(
            """
        SELECT DISTINCT LOWER(category) category
        FROM dim_item
        WHERE category IS NOT NULL
    """
        )
        .df()["category"]
        .tolist()
    )

    manufacturers = (
        con.sql(
            """
        SELECT DISTINCT LOWER(manufacturer_name) manufacturer_name
        FROM dim_item
        WHERE manufacturer_name IS NOT NULL
    """
        )
        .df()["manufacturer_name"]
        .tolist()
    )

    items_df = con.sql("SELECT * FROM dim_item").df()
    sku_lookup = items_df.set_index(items_df["item_id"].str.lower()).to_dict("index")

    pop_df = con.sql("SELECT * FROM item_popularity").df()

    items_by_category = (
        pop_df.sort_values("quantity_60d", ascending=False)
        .groupby("category")["item_id"]
        .apply(list)
        .to_dict()
    )
    items_by_manufacturer = (
        pop_df.sort_values("quantity_60d", ascending=False)
        .groupby("manufacturer_name")["item_id"]
        .apply(list)
        .to_dict()
    )
    items_by_manufacturer_id = (
        pop_df.sort_values("quantity_60d", ascending=False)
        .groupby("manufacturer_id")["item_id"].apply(list).to_dict()
    )

    return ItemSearchIndex(
        categories=sorted(categories),
        manufacturers=sorted(manufacturers),
        sku_lookup=sku_lookup,
        items_by_category=items_by_category,
        items_by_manufacturer=items_by_manufacturer,
        items_by_manufacturer_id=items_by_manufacturer_id,
    )

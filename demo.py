"""Offline detections-to-map pipeline. Coordinates are longitude, latitude."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import box, Point

ROOT = Path(__file__).resolve().parent

def main():
    zones = gpd.read_file(ROOT / "countries.geojson").rename(columns={"name": "zone"})
    raw = json.loads((ROOT / "detections.json").read_text())
    detections = gpd.GeoDataFrame(
        raw, geometry=[box(*d["bbox"]) for d in raw], crs="EPSG:4326")
    detections = detections[detections.confidence >= .65].copy()
    points = detections.copy()
    points.geometry = gpd.GeoSeries([Point((d[0]+d[2])/2, (d[1]+d[3])/2) for d in detections.bbox], index=detections.index, crs=4326)
    joined = gpd.sjoin(points, zones[["zone", "geometry"]], how="left", predicate="within")
    counts = joined.groupby("zone").size()
    zones["detections"] = zones.zone.map(counts).fillna(0).astype(int)
    # Country-scale overview; mock boxes are deliberately tiny, not image-derived.
    fig, ax = plt.subplots(figsize=(13, 7))
    zones.plot(column="detections", cmap="YlOrRd", legend=True, ax=ax,
               edgecolor="#777777", linewidth=.3)
    points.plot(ax=ax, markersize=3, color="#164b78", alpha=.6)
    ax.set(xlim=(-135, 55), ylim=(-60, 75), title="Mock aerial detections by country (confidence >= 0.65)",
           xlabel="Longitude", ylabel="Latitude")
    fig.tight_layout()
    fig.savefig(ROOT / "detections-map.png", dpi=160)
    plt.close(fig)
    # Local metric KNN: projected distances, not Euclidean longitude/latitude.
    local = points.cx[-80:-70, 35:45].to_crs("EPSG:32618")
    query = gpd.GeoSeries([Point(-75.1652, 39.9526)], crs=4326).to_crs(local.crs)
    local["distance_km"] = local.distance(query.iloc[0]) / 1000
    nearest = local.nsmallest(5, "distance_km")
    fig, ax = plt.subplots(figsize=(8, 7))
    local.plot(ax=ax, color="#aaaaaa", markersize=25, label="Candidate detections")
    nearest.plot(ax=ax, color="#d34b25", markersize=65, label="Up to five nearest")
    query.plot(ax=ax, color="#164b78", marker="*", markersize=180, label="Philadelphia query")
    for _, row in nearest.iterrows():
        ax.plot([query.iloc[0].x, row.geometry.x], [query.iloc[0].y, row.geometry.y],
                color="#d34b25", linewidth=.7)
    ax.legend()
    ax.set_title("KNN in UTM 18N: nearest mock detections")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    fig.tight_layout()
    fig.savefig(ROOT / "knn-map.png", dpi=160)
    plt.close(fig)
    assert zones.detections.sum() == joined.zone.notna().sum()
    assert len(nearest) == min(5, len(local))
    nearest[["id", "distance_km"]].to_csv(ROOT / "nearest.csv", index=False)
    zones[["zone", "detections"]].to_csv(ROOT / "zone-counts.csv", index=False)
    print(f"{len(zones)} zones; {len(points)} filtered detections; "
          f"{joined.zone.notna().sum()} assigned; {joined.zone.isna().sum()} outside zones")
    print(nearest[["id", "distance_km"]].to_string(index=False))

if __name__ == "__main__":
    main()

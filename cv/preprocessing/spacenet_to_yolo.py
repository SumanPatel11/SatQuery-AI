import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE = (
    ROOT / "data/raw/cv/building/spacenet2/AOI_3_Paris_Train"
)
DEFAULT_OUTPUT = (
    ROOT / "data/processed/cv/spacenet2_yolo"
)


def clip_boundary(points, axis, boundary, keep_greater):
    """Clip a polygon ring against one image boundary."""

    if not points:
        return []

    output = []
    previous = points[-1]

    def inside(point):
        return (
            point[axis] >= boundary
            if keep_greater
            else point[axis] <= boundary
        )

    for current in points:
        previous_inside = inside(previous)
        current_inside = inside(current)

        if current_inside:
            if not previous_inside:
                output.append(
                    intersection(previous, current, axis, boundary)
                )
            output.append(current)

        elif previous_inside:
            output.append(
                intersection(previous, current, axis, boundary)
            )

        previous = current

    return output


def intersection(a, b, axis, boundary):
    """Calculate intersection between a segment and a boundary."""

    denominator = b[axis] - a[axis]

    if abs(denominator) < 1e-12:
        return a

    ratio = (boundary - a[axis]) / denominator
    other_axis = 1 - axis

    result = [0.0, 0.0]
    result[axis] = boundary
    result[other_axis] = (
        a[other_axis]
        + ratio * (b[other_axis] - a[other_axis])
    )

    return tuple(result)


def clip_polygon(points, width, height):
    """Clip a polygon to the image pixel rectangle."""

    points = list(points)

    points = clip_boundary(points, 0, 0, True)
    points = clip_boundary(points, 0, width, False)
    points = clip_boundary(points, 1, 0, True)
    points = clip_boundary(points, 1, height, False)

    return points


def polygon_area(points):
    if len(points) < 3:
        return 0.0

    return abs(
        sum(
            points[i][0] * points[(i + 1) % len(points)][1]
            - points[(i + 1) % len(points)][0] * points[i][1]
            for i in range(len(points))
        )
    ) / 2.0


def get_polygon_rings(geometry):
    """Return exterior rings for Polygon or MultiPolygon."""

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])

    if geometry_type == "Polygon":
        return [coordinates[0]] if coordinates else []

    if geometry_type == "MultiPolygon":
        return [
            polygon[0]
            for polygon in coordinates
            if polygon
        ]

    raise ValueError(
        f"Unsupported geometry type: {geometry_type}"
    )


def feature_to_bbox(feature, inverse_transform, width, height):
    """Convert a geographic building feature into a clipped pixel bbox."""

    geometry = feature.get("geometry")

    if not geometry:
        return None

    rings = get_polygon_rings(geometry)
    clipped_parts = []

    for ring in rings:
        pixel_points = []

        for coordinate in ring:
            lon, lat = coordinate[:2]
            col, row = inverse_transform * (lon, lat)
            pixel_points.append((col, row))

        clipped = clip_polygon(pixel_points, width, height)

        if len(clipped) >= 3 and polygon_area(clipped) > 1e-8:
            clipped_parts.append(clipped)

    if not clipped_parts:
        return None

    all_points = [
        point
        for polygon in clipped_parts
        for point in polygon
    ]

    x_min = max(0.0, min(p[0] for p in all_points))
    y_min = max(0.0, min(p[1] for p in all_points))
    x_max = min(float(width), max(p[0] for p in all_points))
    y_max = min(float(height), max(p[1] for p in all_points))

    if x_max <= x_min or y_max <= y_min:
        return None

    return x_min, y_min, x_max, y_max


def to_yolo(bbox, width, height):
    x_min, y_min, x_max, y_max = bbox

    x_center = ((x_min + x_max) / 2.0) / width
    y_center = ((y_min + y_max) / 2.0) / height
    box_width = (x_max - x_min) / width
    box_height = (y_max - y_min) / height

    values = [
        min(1.0, max(0.0, x_center)),
        min(1.0, max(0.0, y_center)),
        min(1.0, max(0.0, box_width)),
        min(1.0, max(0.0, box_height)),
    ]

    return "0 " + " ".join(f"{value:.8f}" for value in values)


def convert(source_root, output_root):
    geo_dir = source_root / "geojson" / "buildings"
    image_dir = source_root / "RGB-PanSharpen"
    label_dir = output_root / "labels"

    if not geo_dir.is_dir():
        raise FileNotFoundError(f"GeoJSON directory not found: {geo_dir}")

    if not image_dir.is_dir():
        raise FileNotFoundError(f"Image directory not found: {image_dir}")

    label_dir.mkdir(parents=True, exist_ok=True)

    geo_files = sorted(geo_dir.glob("*.geojson"))

    if not geo_files:
        raise RuntimeError("No GeoJSON annotation files found.")

    stats = {
        "images_processed": 0,
        "features_total": 0,
        "labels_written": 0,
        "empty_annotation_images": 0,
        "features_without_visible_bbox": 0,
        "missing_images": 0,
    }

    metadata_path = output_root / "building_metadata.csv"

    with metadata_path.open(
        "w", newline="", encoding="utf-8"
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "image",
                "feature_index",
                "partialBuilding",
                "partialDec",
                "bbox_visible",
            ],
        )
        writer.writeheader()

        for geo_path in geo_files:
            image_name = geo_path.name.replace(
                "buildings_", "RGB-PanSharpen_"
            ).replace(".geojson", ".tif")

            image_path = image_dir / image_name

            if not image_path.is_file():
                stats["missing_images"] += 1
                continue

            import rasterio

            with rasterio.open(image_path) as src:
                if src.crs is None:
                    raise ValueError(f"Missing CRS: {image_path}")

                if str(src.crs) != "EPSG:4326":
                    raise ValueError(
                        f"Unexpected CRS {src.crs}: {image_path}"
                    )

                width = src.width
                height = src.height
                inverse_transform = ~src.transform

                data = json.loads(geo_path.read_text(encoding="utf-8"))
                features = data.get("features", [])

                label_lines = []

                if not features:
                    stats["empty_annotation_images"] += 1

                for index, feature in enumerate(features):
                    stats["features_total"] += 1

                    bbox = feature_to_bbox(
                        feature,
                        inverse_transform,
                        width,
                        height,
                    )

                    properties = feature.get("properties") or {}

                    writer.writerow({
                        "image": image_name,
                        "feature_index": index,
                        "partialBuilding": properties.get("partialBuilding"),
                        "partialDec": properties.get("partialDec"),
                        "bbox_visible": bbox is not None,
                    })

                    if bbox is None:
                        stats["features_without_visible_bbox"] += 1
                        continue

                    label_lines.append(
                        to_yolo(bbox, width, height)
                    )
                    stats["labels_written"] += 1

                label_path = label_dir / f"{image_path.stem}.txt"

                # Empty files are intentional negative samples.
                label_path.write_text(
                    "\n".join(label_lines),
                    encoding="utf-8",
                )

                stats["images_processed"] += 1

    stats["class_names"] = ["building"]
    stats["source_images"] = len(
        list(image_dir.glob("*.tif"))
    )

    output_root.mkdir(parents=True, exist_ok=True)

    (output_root / "conversion_report.json").write_text(
        json.dumps(stats, indent=2),
        encoding="utf-8",
    )

    print("\nSPACENET2 YOLO CONVERSION REPORT")
    for key, value in stats.items():
        print(f"{key}: {value}")

    print("\nLabels directory:", label_dir)
    print("Metadata CSV:", metadata_path)
    print("Report:", output_root / "conversion_report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert SpaceNet2 GeoJSON buildings to YOLO labels."
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    convert(args.source, args.output)

import os
import argparse
import json
import jsonpickle
import drawsvg as draw
import random
from dacite import from_dict, Config
from export_classes import (
    AssetRef,
    LandscapeSplinesComponent,
    LandscapeSplineSegment,
    SplineMeshComponent,
    Vector2D,
)


class DrawSplines:
    input_path = ""
    image_size = Vector2D(0, 0)
    bound_min = Vector2D(float("inf"), float("inf"))
    bound_max = Vector2D(-float("inf"), -float("inf"))
    components: list[LandscapeSplinesComponent] = []
    segments: list[LandscapeSplineSegment] = []
    spline_meshes: list[SplineMeshComponent] = []
    output_path = ""

    def __init__(self, input_path: str, output_path="", image_size="256x256") -> None:
        self.input_path = input_path
        if output_path:
            self.output_path = output_path
        else:
            self.output_path = input_path.replace(".json", ".svg")
        self.image_size = Vector2D(*list(map(float, image_size.split("x"))))
        pass

    @staticmethod
    def convert_key_explicit(key: str) -> str:
        match key:
            case "Connections":
                return "ConnectionStart"
            case "Connections[1]":
                return "ConnectionEnd"
        return key

    def process(self):
        with open(self.input_path, encoding="utf8") as file:
            data = json.load(file)

        with open("colors.json", encoding="utf8") as file:
            color_dict = json.load(file)
            colors = list(color_dict.keys())

        # parse data
        for obj in data:
            if obj["Type"] == "LandscapeSplinesComponent":
                component = from_dict(LandscapeSplinesComponent, obj)
                self.components.append(component)

            if obj["Type"] == "LandscapeSplineSegment":
                segment = from_dict(
                    LandscapeSplineSegment,
                    obj,
                    Config(convert_key=self.convert_key_explicit),
                )
                self.segments.append(segment)

            if obj["Type"] == "SplineMeshComponent":
                spline_mesh = from_dict(
                    SplineMeshComponent,
                    obj,
                )
                self.spline_meshes.append(spline_mesh)

        # Replace AssetRef with valid LandscapeSplineSegment
        for component in self.components:
            for index, seg in enumerate(component.Properties.Segments):
                if isinstance(seg, AssetRef):
                    for segment in self.segments:
                        if seg.ObjectName.endswith(f"{segment.Name}'"):
                            component.Properties.Segments[index] = segment
                            for point in segment.Properties.SplineInfo.Points:
                                loc = (
                                    point.OutVal + component.Properties.RelativeLocation
                                )
                                self.bound_min.X = min(self.bound_min.X, loc.X)
                                self.bound_min.Y = min(self.bound_min.Y, loc.Y)
                                self.bound_max.X = max(self.bound_max.X, loc.X)
                                self.bound_max.Y = max(self.bound_max.Y, loc.Y)
                            break
            component.Properties.sort_segment()

        # Replace AssetRef with valid SplineMeshComponent
        for segment in self.segments:
            for index, mesh in enumerate(segment.Properties.LocalMeshComponents):
                if isinstance(mesh, AssetRef):
                    for spline_mesh in self.spline_meshes:
                        if mesh.ObjectName.endswith(f"{spline_mesh.Name}'"):
                            segment.Properties.LocalMeshComponents[index] = spline_mesh
                            break

        paths = []
        processed = 0

        print("Bounds:", self.bound_min, self.bound_max)
        self.image_size = self.bound_max - self.bound_min
        canvas = draw.Drawing(self.image_size.X, self.image_size.Y, origin="top-left")

        for i, component in enumerate(self.components):
            coords = []
            random.shuffle(colors)
            path = draw.Path(
                stroke_width=1000, stroke=colors[i], opacity=1, fill="none"
            )
            for index, segment in enumerate(component.Properties.Segments):
                if isinstance(segment, LandscapeSplineSegment):
                    # no_coll = all(
                    #     (
                    #         isinstance(mesh, SplineMeshComponent)
                    #         and mesh.Properties.BodyInstance is None
                    #     )
                    #     for mesh in segment.Properties.LocalMeshComponents
                    # )
                    if index == 0:
                        canvas.append(
                            draw.Text(
                                str(component.Outer),
                                1800,
                                *(
                                    segment.Properties.SplineInfo.Points[0].OutVal
                                    + component.Properties.RelativeLocation
                                    - self.bound_min
                                ).ToVector2D(),
                                fill=colors[i],
                                text_anchor="middle",
                                center=True,
                            )
                        )
                    locs = [
                        (
                            point.OutVal
                            + component.Properties.RelativeLocation
                            - self.bound_min
                        )
                        for point in segment.Properties.SplineInfo.Points
                    ]
                    prev_segment = (
                        component.Properties.Segments[index - 1] if index > 0 else None
                    )
                    if index == 0 or (
                        prev_segment is not None
                        and isinstance(prev_segment, LandscapeSplineSegment)
                        and prev_segment.Properties.SplineInfo.Points[1].OutVal
                        != segment.Properties.SplineInfo.Points[0].OutVal
                    ):
                        path.M(*locs[0].ToVector2D())
                    path.L(*locs[1].ToVector2D())
                    # canvas.append(
                    #     draw.Text(
                    #         str(index),
                    #         1800,
                    #         *loc_2d,
                    #         fill="red",
                    #         text_anchor="middle",
                    #         center=True,
                    #     )
                    # )
            canvas.insert(1, path)
            processed += 1

        # print(jsonpickle.encode(coords, unpicklable=False))
        canvas.extend(paths)
        target_size = 256.0
        scale_fac = target_size / self.image_size.Y
        canvas.set_render_size(self.image_size.X * scale_fac, target_size)
        canvas.save_svg(self.output_path)
        print(f"Generated {processed} components")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UE landscape SVG exporter")
    parser.add_argument(
        "--input", "-i", type=str, required=True, help="Path to the map JSON file"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=False,
        help="SVG image output path",
    )
    parser.add_argument(
        "--dimension",
        "-d",
        type=str,
        required=False,
        default="256x256",
        help="SVG image output dimension",
    )
    args = parser.parse_args()
    ds = DrawSplines(args.input, output_path=args.output, image_size=args.dimension)
    ds.process()

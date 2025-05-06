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

    def sort_spline_mesh(self):
        # Create dictionaries to map from InValue to index and OutValue to index
        in_value_map: dict[tuple[float, float, float], int] = {}
        out_value_map: dict[tuple[float, float, float], int] = {}

        for i, item in enumerate(self.spline_meshes):
            # Convert the dictionaries to tuples for hashability
            in_tuple = (
                item.Properties.SplineParams.StartPos.X,
                item.Properties.SplineParams.StartPos.Y,
                item.Properties.SplineParams.StartPos.Z,
            )
            out_tuple = (
                item.Properties.SplineParams.EndPos.X,
                item.Properties.SplineParams.EndPos.Y,
                item.Properties.SplineParams.EndPos.Z,
            )

            # Calculate bounds from spline mesh components as well
            start_pos = (
                item.Properties.SplineParams.StartPos + item.Properties.RelativeLocation
            )
            end_pos = (
                item.Properties.SplineParams.EndPos + item.Properties.RelativeLocation
            )
            self.bound_min.X = min(self.bound_min.X, start_pos.X, end_pos.X)
            self.bound_min.Y = min(self.bound_min.Y, start_pos.Y, end_pos.Y)
            self.bound_max.X = max(self.bound_max.X, start_pos.X, end_pos.X)
            self.bound_max.Y = max(self.bound_max.Y, start_pos.Y, end_pos.Y)

            in_value_map[in_tuple] = i
            out_value_map[out_tuple] = i

        # Find starting points (points that have an InValue that doesn't match any OutValue)
        starting_indices: list[int] = []
        for i, item in enumerate(self.spline_meshes):
            in_tuple = (
                item.Properties.SplineParams.StartPos.X,
                item.Properties.SplineParams.StartPos.Y,
                item.Properties.SplineParams.StartPos.Z,
            )
            if in_tuple not in out_value_map:
                starting_indices.append(i)

        # Create chains starting from each starting point
        chains: list[list[int]] = []
        for start_idx in starting_indices:
            chain = [start_idx]
            current_idx = start_idx

            while True:
                current_item = self.spline_meshes[current_idx]
                out_tuple = (
                    current_item.Properties.SplineParams.EndPos.X,
                    current_item.Properties.SplineParams.EndPos.Y,
                    current_item.Properties.SplineParams.EndPos.Z,
                )

                if out_tuple in in_value_map:
                    next_idx = in_value_map[out_tuple]
                    chain.append(next_idx)
                    current_idx = next_idx
                else:
                    # End of chain
                    break
            else:
                break

            chains.append(chain)

        # Sort chains by length (longest first)
        chains.sort(key=len, reverse=True)

        # Combine all chains into a single ordered list
        ordered_indices: list[int] = []
        for chain in chains:
            ordered_indices.extend(chain)

        # Find any points not included in any chain
        all_indices = set(range(len(self.spline_meshes)))
        orphaned_indices = list(all_indices - set(ordered_indices))
        ordered_indices.extend(orphaned_indices)

        # Create the sorted data
        self.spline_meshes = [self.spline_meshes[i] for i in ordered_indices]

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

        # Replace AssetRef with valid LandscapeSplineSegment
        for component in self.components:
            for index, seg in enumerate(component.Properties.Segments):
                if isinstance(seg, AssetRef):
                    segment = from_dict(
                        LandscapeSplineSegment,
                        seg.get_object(data),
                        Config(convert_key=self.convert_key_explicit),
                    )
                    component.Properties.Segments[index] = segment
                    for point in segment.Properties.SplineInfo.Points:
                        loc = point.OutVal + component.Properties.RelativeLocation
                        self.bound_min.X = min(self.bound_min.X, loc.X)
                        self.bound_min.Y = min(self.bound_min.Y, loc.Y)
                        self.bound_max.X = max(self.bound_max.X, loc.X)
                        self.bound_max.Y = max(self.bound_max.Y, loc.Y)

            component.Properties.sort_segment()

        processed = 0

        print("Bounds:", self.bound_min, self.bound_max)
        self.image_size = self.bound_max - self.bound_min
        padding = 5000
        canvas = draw.Drawing(
            self.image_size.X + padding, self.image_size.Y + padding, origin="top-left"
        )

        coords = []
        for i, component in enumerate(self.components):
            random.shuffle(colors)
            path = draw.Path(
                stroke_width=1000, stroke=colors[i], opacity=1, fill="none"
            )
            for index, segment in enumerate(component.Properties.Segments):
                if isinstance(segment, LandscapeSplineSegment):
                    if index == 0:
                        canvas.append(
                            draw.Text(
                                str(component.Outer),
                                1800,
                                *(
                                    segment.Properties.SplineInfo.Points[0].OutVal
                                    + component.Properties.RelativeLocation
                                    - self.bound_min
                                    + padding / 2
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
                            + padding / 2
                        )
                        for point in segment.Properties.SplineInfo.Points
                    ]
                    ctrl_scale = 0.5
                    ctrl_start = (
                        segment.Properties.SplineInfo.Points[0].LeaveTangent
                        * ctrl_scale
                        + locs[0]
                    )
                    ctrl_end = (
                        locs[1]
                        - segment.Properties.SplineInfo.Points[1].ArriveTangent
                        * ctrl_scale
                    )
                    # canvas.append(
                    #     draw.Line(
                    #         *locs[0].ToVector2D(),
                    #         *ctrl_start.ToVector2D(),
                    #         stroke="red",
                    #         stroke_width=100,
                    #     )
                    # )
                    # canvas.append(
                    #     draw.Line(
                    #         *locs[1].ToVector2D(),
                    #         *ctrl_end.ToVector2D(),
                    #         stroke="blue",
                    #         stroke_width=100,
                    #     )
                    # )
                    # canvas.append(
                    #     draw.Circle(*ctrl_start.ToVector2D(), r=200, fill="red")
                    # )
                    # canvas.append(
                    #     draw.Circle(*ctrl_end.ToVector2D(), r=200, fill="blue")
                    # )
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
                        path.C(
                            *ctrl_start.ToVector2D(),
                            *ctrl_end.ToVector2D(),
                            *locs[1].ToVector2D(),
                        )
                        # canvas.append(
                        #     draw.Circle(*locs[0].ToVector2D(), r=200, fill="red")
                        # )
                    else:
                        path.S(
                            *ctrl_end.ToVector2D(),
                            *locs[1].ToVector2D(),
                        )
                    coords.append(locs[1])
                    # canvas.append(draw.Circle(*locs[1].ToVector2D(), r=200, fill="red"))
            canvas.insert(1, path)
            processed += 1

        # print(jsonpickle.encode(coords, unpicklable=False))
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

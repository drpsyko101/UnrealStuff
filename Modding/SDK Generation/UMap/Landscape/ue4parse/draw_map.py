import argparse
import drawsvg as draw
import json
import logging
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dacite import from_dict, Config
from export_classes import (
    AssetRef,
    LandscapeSplinesComponent,
    LandscapeSplineSegment,
    Log,
    SplineMeshComponent,
    Vector2D,
)
from multiprocessing import cpu_count
from pathlib import Path

_logger = logging.getLogger(__name__)


class DrawSplines:
    def __init__(
        self,
        input_path: str,
        output_path="",
        image_size="",
        offset="",
        scale=0,
        workers=0,
        colors_path="",
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path or input_path.replace(".json", ".svg")
        self.image_size = (
            Vector2D(*list(map(float, image_size.split(","))))
            if image_size
            else Vector2D.zeroVector()
        )
        self.offset = (
            Vector2D(*list(map(float, offset.split(","))))
            if offset
            else Vector2D.zeroVector()
        )
        self.scale = scale
        self.workers = workers or cpu_count()
        self.bound_min = Vector2D(float("inf"), float("inf"))
        self.bound_max = Vector2D(-float("inf"), -float("inf"))
        self.colors_path = colors_path

    @staticmethod
    def _convert_key_explicit(key: str) -> str:
        match key:
            case "Connections":
                return "ConnectionStart"
            case "Connections[1]":
                return "ConnectionEnd"
        return key

    def _parse_data(self, data: list) -> list[LandscapeSplinesComponent]:
        """Parse array into known UE objects"""
        spline_components = [
            from_dict(LandscapeSplinesComponent, obj)
            for obj in data
            if obj["Type"] == "LandscapeSplinesComponent"
            and "Segments" in obj["Properties"]  # Make sure it has valid segments
        ]

        # Skip empty spline components
        if not spline_components:
            return []

        for component in spline_components:
            if component.Properties.Segments is None:
                continue
            segments = [
                from_dict(
                    LandscapeSplineSegment,
                    seg.get_object(data),
                    Config(convert_key=self._convert_key_explicit),
                )
                for seg in component.Properties.Segments
                if isinstance(seg, AssetRef)
            ]
            component.Properties.Segments = segments

            # Skip empty segments
            if not segments:
                continue

            for segment in segments:
                if segment.Properties.LocalMeshComponents is None:
                    continue
                mesh_components = [
                    from_dict(SplineMeshComponent, comp.get_object(data))
                    for comp in segment.Properties.LocalMeshComponents
                    if isinstance(comp, AssetRef)
                ]
                if not mesh_components:
                    continue

                segment.Properties.LocalMeshComponents = mesh_components

            component.Properties.sort_segment()

        return spline_components

    def _plot_path(
        self, components: list[LandscapeSplinesComponent], colors: dict[str, str] = {}
    ):
        _logger.info("Bounds: Min=%s Max=%s", self.bound_min, self.bound_max)
        self.image_size = (
            (self.bound_max - self.bound_min)
            if self.image_size == Vector2D.zeroVector()
            else self.image_size
        )
        self.offset = (
            self.bound_min
            if self.offset == Vector2D.zeroVector()
            else self.offset
        )
        canvas = draw.Drawing(self.image_size.X, self.image_size.Y, origin="top-left")

        color = "gray"
        processed = 0
        for i, component in enumerate(components):
            # Skip invalid segments
            if (
                component.Properties.Segments is None
                or not component.Properties.Segments
            ):
                continue

            path: draw.Path | None = None
            for index, segment in enumerate(component.Properties.Segments):
                if isinstance(segment, LandscapeSplineSegment):
                    locs = [
                        (
                            point.OutVal
                            + component.Properties.RelativeLocation
                            - self.offset
                        )
                        for point in segment.Properties.SplineInfo.Points
                    ]
                    ctrl_scale = 0.2
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
                    if _logger.isEnabledFor(Log.DEBUG.value):
                        canvas.append(
                            draw.Line(
                                *locs[0].ToVector2D(),
                                *ctrl_start.ToVector2D(),
                                stroke="red",
                                stroke_width=100,
                            )
                        )
                        canvas.append(
                            draw.Line(
                                *locs[1].ToVector2D(),
                                *ctrl_end.ToVector2D(),
                                stroke="blue",
                                stroke_width=100,
                            )
                        )
                        canvas.append(
                            draw.Circle(*ctrl_start.ToVector2D(), r=200, fill="red")
                        )
                        canvas.append(
                            draw.Circle(*ctrl_end.ToVector2D(), r=200, fill="blue")
                        )
                    prev_segment = (
                        component.Properties.Segments[index - 1] if index > 0 else None
                    )

                    mesh_name = (
                        segment.Properties.LocalMeshComponents[
                            0
                        ].Properties.StaticMesh.ObjectName
                        if segment.Properties.LocalMeshComponents is not None
                        and isinstance(
                            segment.Properties.LocalMeshComponents[0],
                            SplineMeshComponent,
                        )
                        and segment.Properties.LocalMeshComponents[
                            0
                        ].Properties.StaticMesh
                        is not None
                        else ""
                    )

                    color = colors[mesh_name] if colors else color

                    # Check if we need to start a new path
                    if index == 0 or (
                        prev_segment is not None
                        and isinstance(prev_segment, LandscapeSplineSegment)
                        and prev_segment.Properties.SplineInfo.Points[1].OutVal
                        != segment.Properties.SplineInfo.Points[0].OutVal
                    ):
                        # Insert previous path if valid
                        if path is not None:
                            canvas.insert(1, path)

                        path = draw.Path(
                            stroke_width=2000, stroke=color, opacity=1, fill="none"
                        )
                        path.M(*locs[0].ToVector2D())
                        path.C(
                            *ctrl_start.ToVector2D(),
                            *ctrl_end.ToVector2D(),
                            *locs[1].ToVector2D(),
                        )
                        if _logger.isEnabledFor(Log.DEBUG.value):
                            canvas.append(
                                draw.Text(
                                    str(component.Outer),
                                    1800,
                                    *(
                                        segment.Properties.SplineInfo.Points[0].OutVal
                                        + component.Properties.RelativeLocation
                                        - self.offset
                                    ).ToVector2D(),
                                    fill=color,
                                    text_anchor="middle",
                                    center=True,
                                )
                            )
                            canvas.append(
                                draw.Circle(*locs[0].ToVector2D(), r=200, fill="red")
                            )
                    else:
                        if path is not None:
                            path.S(
                                *ctrl_end.ToVector2D(),
                                *locs[1].ToVector2D(),
                            )
                    if _logger.isEnabledFor(Log.DEBUG.value):
                        canvas.append(
                            draw.Circle(*locs[1].ToVector2D(), r=200, fill="red")
                        )

            # Insert final path if valid
            if path is not None:
                canvas.insert(1, path)

            processed += 1

        _logger.info("Generated %i paths", processed)
        scale_fac = self.scale / self.image_size.Y
        canvas.set_render_size(self.image_size.X * scale_fac, self.scale)
        canvas.save_svg(self.output_path)
        _logger.info("SVG saved at %s", Path(self.output_path).absolute())

    def _process_file(self, file_path: Path) -> list:
        try:
            with file_path.open(encoding="utf8") as content:
                raw_data = json.load(content)
                return self._parse_data(raw_data)
        except Exception as e:
            _logger.error("Error processing %s: %s", file_path, e)
            return []

    def _collect_file_paths(self) -> list[Path]:
        file_paths = []
        main_file_path = Path(self.input_path)
        file_paths.append(main_file_path)

        basename = main_file_path.stem
        generated_path = main_file_path.parent.joinpath(basename, "_Generated_")
        if generated_path.exists():
            file_paths.extend(list(generated_path.glob("*.json")))

        return file_paths

    def process(self):
        components: list[LandscapeSplinesComponent] = []
        file_paths = self._collect_file_paths()
        _logger.info("Collected %i files to process", len(file_paths))

        with ProcessPoolExecutor(max_workers=self.workers) as executor:
            results = list(executor.map(self._process_file, file_paths))

            for result in results:
                components.extend(result)

        colors: dict[str, str] = {}
        if self.colors_path:
            try:
                with open(self.colors_path, encoding="utf8") as file:
                    colors = json.load(file)
            except Exception:
                pass

        if self.image_size == Vector2D.zeroVector():
            locations = [
                point.OutVal + component.Properties.RelativeLocation
                for component in components
                for segment in component.Properties.Segments
                if isinstance(segment, LandscapeSplineSegment)
                for point in segment.Properties.SplineInfo.Points
            ]
            self.bound_min.X = min(self.bound_min.X, *[v.X for v in locations])
            self.bound_min.Y = min(self.bound_min.Y, *[v.Y for v in locations])
            self.bound_max.X = max(self.bound_max.X, *[v.X for v in locations])
            self.bound_max.Y = max(self.bound_max.Y, *[v.Y for v in locations])

        self._plot_path(components, colors)


if __name__ == "__main__":
    start_time = time.perf_counter()
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
        default="256,256",
        help="SVG image output dimension i.e. 256,256",
    )
    parser.add_argument(
        "--offset",
        "-O",
        type=str,
        required=False,
        default="0,0",
        help="Manual offset for the top left corner of the image i.e. 0,0. Only applied when using --dimension",
    )
    parser.add_argument(
        "--scale",
        "-s",
        type=int,
        required=False,
        default=256,
        help="Set the render scale of the SVG image",
    )
    parser.add_argument(
        "--log",
        "-l",
        type=lambda log: Log[log],
        choices=list(Log),
        required=False,
        default="INFO",
        help="Logging level to display in STDOUT",
    )
    parser.add_argument(
        "--worker",
        "-w",
        type=int,
        required=False,
        default=0,
        help="Amount of CPU thread to use. Setting it to 0 will use all available CPU threads.",
    )
    parser.add_argument(
        "--color",
        "-c",
        type=str,
        required=False,
        help="Path to the mesh colors JSON file",
    )
    args = parser.parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s: %(message)s", level=args.log.value
    )
    ds = DrawSplines(
        args.input,
        output_path=args.output,
        image_size=args.dimension,
        offset=args.offset,
        scale=args.scale,
        workers=args.worker,
        colors_path=args.color,
    )
    ds.process()

    _logger.info("Process completed in %f seconds", time.perf_counter() - start_time)

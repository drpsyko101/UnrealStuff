from dataclasses import dataclass, field
import json
from typing import Optional
from numpy import asarray
import numpy as np
from enum import Enum
import re
import logging


@dataclass
class Vector2D:
    X: float
    Y: float

    # ndarr: np.ndarray = np.ndarray((0,4), np.float32)
    def __post_init__(self):
        self.ndarr = asarray(list(self.__dict__.values()))

    def __add__(self, B):
        if not isinstance(B, Vector2D):
            raise TypeError
        return Vector2D(self.X + B.X, self.Y + B.Y)

    def __sub__(self, B):
        if not isinstance(B, Vector2D):
            raise TypeError
        return Vector2D(self.X - B.X, self.Y - B.Y)

    def __iter__(self):
        return iter([self.X, self.Y])

    def __truediv__(self, B):
        if isinstance(B, Vector2D):
            return Vector2D(self.X / B.X, self.Y / B.Y)
        elif isinstance(B, float) or isinstance(B, int):
            return Vector2D(self.X / B, self.Y / B)
        else:
            return TypeError

    def __str__(self) -> str:
        return f"(X: {self.X}, Y: {self.Y})"

    @staticmethod
    def min(A, B):
        return Vector2D(min(A.X, B.X), min(A.Y, B.Y))


@dataclass
class Vector3D(Vector2D):
    Z: float

    def __iter__(self):
        return [self.X, self.Y, self.Z]

    def __sub__(self, B):
        if isinstance(B, Vector3D):
            return Vector3D(self.X - B.X, self.Y - B.Y, self.Z - B.Z)
        elif isinstance(B, Vector2D):
            return Vector3D(self.X - B.X, self.Y - B.Y, self.Z)
        else:
            raise TypeError

    def __add__(self, B):
        if isinstance(B, Vector3D):
            return Vector3D(self.X + B.X, self.Y + B.Y, self.Z + B.Z)
        elif isinstance(B, Vector2D):
            return Vector3D(self.X + B.X, self.Y + B.Y, self.Z)
        elif isinstance(B, float) or isinstance(B, int):
            return Vector3D(self.X + B, self.Y + B, self.Z + B)
        else:
            raise TypeError

    def __mul__(self, B):
        if isinstance(B, Vector3D):
            return Vector3D(self.X * B.X, self.Y * B.Y, self.Z * B.Z)
        if isinstance(B, float) or isinstance(B, int):
            return Vector3D(self.X * B, self.Y * B, self.Z * B)
        else:
            raise TypeError

    def __truediv__(self, B):
        if isinstance(B, Vector3D):
            return Vector3D(self.X / B.X, self.Y / B.Y, self.Z / B.Z)
        elif isinstance(B, float) or isinstance(B, int):
            return Vector3D(self.X / B, self.Y / B, self.Z / B)
        return super().__truediv__(B)

    def ToVector2D(self):
        return Vector2D(self.X, self.Y)

    def scale_relative_to(self, B, scale=1.0):
        if isinstance(B, Vector3D):
            offset = B - self
            scaled = offset * scale
            return self + scaled
        else:
            raise TypeError


@dataclass
class Vector4D(Vector3D):
    W: float


@dataclass
class Rotator:
    Pitch: float
    Yaw: float
    Roll: float

    def __post_init__(self):
        self.ndarr = asarray(list(self.__dict__.values()))


@dataclass
class PathName:
    ObjectName: str = ""
    ObjectPath: str = ""
    Outer: str = ""
    AssetType: str = field(init=False)
    AssetName: str = field(init=False)
    Context: str = field(init=False, default="N/A")
    SubObject: str = field(init=False, default="N/A")

    def __post_init__(self):
        if self.ObjectName[-1] == "'":
            self.AssetName = self.ObjectName.split("'")[-2].split(".")[-1]
        else:
            self.AssetName = self.ObjectName.split(".")[-1]

        self.AssetType = self.ObjectName.split("'")[0]

        if ":" in self.ObjectName:
            parts = self.ObjectName.split(":")
            if len(parts) > 1:
                self.Context = parts[1]


@dataclass
class Export:
    Type: str
    Name: str
    Outer: Optional[str]


## Landscape Component
@dataclass
class Allocations:
    LayerInfo: PathName
    WeightmapTextureIndex: int
    WeightmapTextureChannel: int


@dataclass
class LandscapeComponentProperties:
    ComponentSizeQuads: int
    SubsectionSizeQuads: int
    NumSubsections: int
    HeightmapTexture: PathName
    HeightmapScaleBias: Vector4D
    WeightmapScaleBias: Vector4D
    MaterialInstances: list[PathName]
    WeightmapTextures: Optional[list[PathName]] = field(default_factory=list)
    WeightmapLayerAllocations: Optional[list[Allocations]] = field(default_factory=list)
    SectionBaseX: int = 0
    SectionBaseY: int = 0
    RelativeLocation: Vector3D = field(default_factory=lambda: Vector3D(0, 0, 0))

    def __post_init__(self):
        if self.SectionBaseX is None:
            self.SectionBaseX = 0
        if self.SectionBaseY is None:
            self.SectionBaseY = 0
        self.SectionBase = Vector2D(self.SectionBaseX, self.SectionBaseY)


@dataclass
class LSCExport(Export):
    Properties: LandscapeComponentProperties
    Class: str = None


## Texture
@dataclass
class TextureProperties:
    AddressX: str
    AddressY: str
    ImportedSize: Vector2D
    LightingGuid: str
    LODGroup: str
    SRGB: bool


@dataclass
class Texture2DExport(Export):
    Properties: TextureProperties
    Class: str = None


## Material instance
@dataclass
class ParameterInfo:
    Name: str
    Association: str
    Index: int


@dataclass
class TerrainLayerWeightParameters:
    WeightmapIndex: int
    bWeightBasedBlend: bool
    ParameterInfo: ParameterInfo


@dataclass
class ParameterValue:
    R: float
    G: float
    B: float
    A: float
    Hex: str


@dataclass
class VectorParameterValue:
    ParameterInfo: ParameterInfo
    ParameterValue: ParameterValue


@dataclass
class StaticParameters:
    TerrainLayerWeightParameters: list[TerrainLayerWeightParameters]


@dataclass
class LandscapeMaterialInstanceConstantProperties:
    StaticParameters: Optional[dict[str, list[TerrainLayerWeightParameters]]]
    VectorParameterValues: Optional[list[VectorParameterValue]]


@dataclass
class LMICExport(Export):  # LandscapeMaterialInstanceConstant
    Properties: Optional[LandscapeMaterialInstanceConstantProperties]
    Class: str = None


## Landscape
@dataclass
class LandscapeProperties:
    LandscapeGuid: str
    LandscapeMaterial: PathName
    LandscapeComponents: list[PathName]
    ComponentSizeQuads: int
    SubsectionSizeQuads: int
    NumSubsections: int


@dataclass
class LandscapeExport(Export):
    Properties: Optional[LandscapeProperties] = field(init=False, default=None)
    Class: str = None


## Scene Component
@dataclass
class SceneComponentProperties:
    RelativeLocation: Vector3D
    RelativeRotation: Rotator = field(default_factory=lambda: Rotator(0, 0, 0))
    RelativeScale3D: Vector3D = field(default_factory=lambda: Vector3D(1, 1, 1))


@dataclass
class SceneComponentExport(Export):
    Properties: SceneComponentProperties
    Class: str = None


class ExportsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(ExportsEncoder, self).default(obj)


@dataclass
class AssetRef:
    ObjectName: str
    ObjectPath: str

    def get_object(self, data: list):
        index = int(self.ObjectPath.split(".")[-1])
        return data[index]


@dataclass
class SplineConnection:
    ControlPoint: AssetRef
    TangentLen: float


class CurveInterpMode(Enum):
    # A straight line between two keypoint values.
    CIM_Linear = 1
    # A cubic-hermite curve between two keypoints, using Arrive/Leave tangents. These tangents will be automatically
    # updated when points are moved, etc.  Tangents are unclamped and will plateau at curve start and end points.
    CIM_CurveAuto = 2
    # The out value is held constant until the next key, then will jump to that value.
    CIM_Constant = 3
    # A smooth curve just like CIM_Curve, but tangents are not automatically updated so you can have manual control over them (eg. in Curve Editor).
    CIM_CurveUser = 4
    # A curve like CIM_Curve, but the arrive and leave tangents are not forced to be the same, so you can create a 'corner' at this key.
    CIM_CurveBreak = 5
    # A cubic-hermite curve between two keypoints, using Arrive/Leave tangents. These tangents will be automatically
    # updated when points are moved, etc.  Tangents are clamped and will plateau at curve start and end points.
    CIM_CurveAutoClamped = 6
    # Invalid or unknown curve type.
    CIM_Unknown = 7


@dataclass
class SplinePoint:
    InVal: float = 0.0
    OutVal: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    ArriveTangent: Vector3D = field(default_factory=lambda: Vector3D(0, 0, 0))
    LeaveTangent: Vector3D = field(default_factory=lambda: Vector3D(0, 0, 0))
    InterpMode: CurveInterpMode | str = CurveInterpMode.CIM_Unknown

    def __post_init__(self):
        if isinstance(self.InterpMode, str):
            interp = re.sub(r"^.*::", "", self.InterpMode)
            self.InterpMode = CurveInterpMode[interp]


@dataclass
class SplineInfoData:
    Points: list[SplinePoint]


@dataclass
class SegmentPoint:
    Center: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    Left: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    Right: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    FalloffLeft: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    FalloffRight: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    LayerLeft: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    LayerRight: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    LayerFalloffLeft: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    LayerFalloffRight: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    StartEndFalloff: float = 0.0


@dataclass
class SplineBounds:
    Min: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    Max: Vector3D = field(
        default_factory=lambda: field(default_factory=lambda: Vector3D(0, 0, 0))
    )
    IsValid: int = 0


@dataclass
class SplineParameter:
    StartPos: Vector3D
    StartTangent: Vector3D
    StartScale: Optional[Vector2D]
    StartOffset: Optional[Vector2D]
    EndPos: Vector3D
    EndTangent: Vector3D
    EndScale: Optional[Vector2D]
    EndOffset: Optional[Vector2D]


class ECollisionEnabled(Enum):
    NoCollision = 0
    QueryOnly = 1
    PhysicsOnly = 2
    QueryAndPhysics = 3
    ProbeOnly = 4
    QueryAndProbe = 5


@dataclass
class MeshBodyInstance:
    CollisionEnabled: Optional[ECollisionEnabled | str]
    CollisionProfileName: Optional[str]
    bAutoWeld: Optional[bool]

    def __post_init__(self):
        if isinstance(self.CollisionEnabled, str):
            coll = re.sub(r"^.*::", "", self.CollisionEnabled)
            self.CollisionEnabled = ECollisionEnabled[coll]


@dataclass
class SplineMeshComponentProperty:
    SplineParams: SplineParameter
    CachedMeshBodySetupGuid: str
    BodySetup: AssetRef
    bNeverNeedsCookedCollisionData: Optional[bool]
    StaticMesh: Optional[AssetRef]
    CastShadow: Optional[bool]
    BodyInstance: Optional[MeshBodyInstance]
    bHasNoStreamableTextures: Optional[bool]
    AttachParent: AssetRef
    RelativeLocation: Vector3D
    bVisible: Optional[bool]
    bHiddenInGame: Optional[bool]


@dataclass
class SplineMeshComponent(Export):
    Class: str
    Flags: str
    Properties: SplineMeshComponentProperty


@dataclass
class SplineSegmentProperty:
    ConnectionStart: Optional[SplineConnection]
    ConnectionEnd: Optional[SplineConnection]
    SplineInfo: SplineInfoData
    Points: list[SegmentPoint]
    Bounds: SplineBounds
    LocalMeshComponents: Optional[list[AssetRef | SplineMeshComponent]]


@dataclass
class LandscapeSplineSegment(Export):
    Class: str
    Flags: str
    Properties: SplineSegmentProperty


@dataclass
class SplineComponentProperty:
    ControlPoints: Optional[list[AssetRef]]
    Segments: list[AssetRef | LandscapeSplineSegment] | list[LandscapeSplineSegment]
    RelativeLocation: Vector3D

    # Sort segments into connected chains
    def sort_segment(self):
        if self.Segments is None:
            return

        # Create dictionaries to map from InValue to index and OutValue to index
        in_value_map: dict[tuple[float, float, float], int] = {}
        out_value_map: dict[tuple[float, float, float], int] = {}

        for i, item in enumerate(self.Segments):
            if isinstance(item, LandscapeSplineSegment):
                # Convert the dictionaries to tuples for hashability
                in_tuple = (
                    item.Properties.SplineInfo.Points[0].OutVal.X,
                    item.Properties.SplineInfo.Points[0].OutVal.Y,
                    item.Properties.SplineInfo.Points[0].OutVal.Z,
                )
                out_tuple = (
                    item.Properties.SplineInfo.Points[1].OutVal.X,
                    item.Properties.SplineInfo.Points[1].OutVal.Y,
                    item.Properties.SplineInfo.Points[1].OutVal.Z,
                )

                in_value_map[in_tuple] = i
                out_value_map[out_tuple] = i

        # Find starting points (points that have an InValue that doesn't match any OutValue)
        starting_indices: list[int] = []
        for i, item in enumerate(self.Segments):
            if isinstance(item, LandscapeSplineSegment):
                in_tuple = (
                    item.Properties.SplineInfo.Points[0].OutVal.X,
                    item.Properties.SplineInfo.Points[0].OutVal.Y,
                    item.Properties.SplineInfo.Points[0].OutVal.Z,
                )
                if in_tuple not in out_value_map:
                    starting_indices.append(i)

        # Create chains starting from each starting point
        chains: list[list[int]] = []
        for start_idx in starting_indices:
            chain = [start_idx]
            current_idx = start_idx
            visited_indices = {start_idx}

            while True:
                current_item = self.Segments[current_idx]
                if isinstance(current_item, LandscapeSplineSegment):
                    out_tuple = (
                        current_item.Properties.SplineInfo.Points[1].OutVal.X,
                        current_item.Properties.SplineInfo.Points[1].OutVal.Y,
                        current_item.Properties.SplineInfo.Points[1].OutVal.Z,
                    )

                    if out_tuple in in_value_map:
                        next_idx = in_value_map[out_tuple]

                        # Check if we've already visited this index
                        if next_idx in visited_indices:
                            break

                        chain.append(next_idx)
                        visited_indices.add(next_idx)
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
        all_indices = set(range(len(self.Segments)))
        orphaned_indices = list(all_indices - set(ordered_indices))
        ordered_indices.extend(orphaned_indices)

        # Create the sorted data
        self.Segments = [self.Segments[i] for i in ordered_indices]


@dataclass
class LandscapeSplinesComponent(Export):
    Class: str
    Flags: str
    Properties: SplineComponentProperty


class Log(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    WARN = logging.WARN
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    def __str__(self) -> str:
        return self.name

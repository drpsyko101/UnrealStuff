import argparse
import json
from pathlib import Path


class MeshColor:
    def __init__(self, path: str, output: str = "output.json"):
        self.path = Path(path)
        self.output = Path(output)

    def _parser(self, path: Path):
        cols: dict[str, str] = {}
        with open(path, encoding="utf8") as content:
            data = json.load(content)
            for obj in data:
                if (
                    obj["Type"] == "SplineMeshComponent"
                    and "Properties" in obj
                    and "StaticMesh" in obj["Properties"]
                    and "ObjectName" in obj["Properties"]["StaticMesh"]
                ):
                    cols[obj["Properties"]["StaticMesh"]["ObjectName"]] = ""
        return cols

    def process(self):
        cols: dict[str, str] = {}
        cols.update(self._parser(self.path))

        generated_path = self.path.parent.joinpath(self.path.stem + "_Generated_")
        if generated_path.exists():
            for file in generated_path.glob("*.json"):
                cols.update(self._parser(file))

        print(f"Found {len(cols)} meshes")
        json.dump(cols, open(self.output, "w", encoding="utf8"), indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UE4 Asset processing script.")
    parser.add_argument(
        "--input", "-i", type=str, required=True, help="Map JSON dump file"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=False,
        default="output.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    mc = MeshColor(args.input, args.output)
    mc.process()

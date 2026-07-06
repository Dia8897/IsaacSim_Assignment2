import json
from pathlib import Path

class AssetManager:
    def load_assets(self, config_path:str,project_root:str)->list[dict]:
        config_path=Path(config_path) #convert the string into a Path object
        project_root=Path(project_root)
        if not config_path.exists():
            raise FileNotFoundError(f"Asset config file not found: {config_path}")
        with config_path.open("r",encoding="utf-8") as file:
            data=json.load(file) # read the file and convert the json text into python objects
        
        if "assets" not in data:
            raise ValueError("The json file must contain assets section")
        if not isinstance(data["assets"],list):
            raise TypeError("assets must be a list")
        validated_assets=[]
        for asset in data["assets"]:
            if "label" not in asset:
                raise ValueError("Asset must have a label")
            if "path" not in asset:
                raise ValueError("Asset must have a path")
            label=asset["label"]
            path=asset["path"]
            if not isinstance(label,str) or not label.strip():
                raise ValueError("Label must be a non empty string")
            if not isinstance(path, str) or not path.strip():
                raise ValueError("Path must be a non empty string")
            asset_path=project_root/path
            if not asset_path.exists():
                raise FileNotFoundError(f"Asset file not found: {asset_path}")
            validated_assets.append({
                "label":label.strip(),
                "path":str(asset_path)
            }
            )
        return validated_assets

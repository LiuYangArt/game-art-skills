import os

import unreal


def log(message):
    unreal.log(f"[CodexProbe] {message}")


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def safe_get(obj, prop_name, default=None):
    try:
        return obj.get_editor_property(prop_name)
    except Exception:
        return default


def main():
    asset_path = os.environ.get("UE_ASSET_PATH", "").strip()
    if not asset_path:
        raise RuntimeError("UE_ASSET_PATH is required")

    property_filter = os.environ.get("UE_PROPERTY_FILTER", "").strip().lower()
    recompile_material = env_flag("UE_RECOMPILE_MATERIAL", default=False)
    show_dir = env_flag("UE_SHOW_DIR", default=True)

    asset = unreal.load_asset(asset_path)
    if not asset:
        raise RuntimeError(f"Could not load asset: {asset_path}")

    log(f"Loaded asset: {asset.get_path_name()}")
    log(f"Asset class: {asset.get_class().get_name()}")

    if show_dir:
        names = dir(asset)
        if property_filter:
            names = [name for name in names if property_filter in name.lower()]
        log(f"Matching attribute count: {len(names)}")
        for name in names[:200]:
            unreal.log(f"[CodexProbe][Attr] {name}")

    editor_only_data = safe_get(asset, "editor_only_data", None)
    log(f"Has editor_only_data: {editor_only_data is not None}")

    compile_methods = [name for name in dir(asset) if "compile" in name.lower() or "recomp" in name.lower()]
    log(f"Asset compile-like methods: {compile_methods}")

    material_lib = getattr(unreal, "MaterialEditingLibrary", None)
    if material_lib:
        methods = [name for name in dir(material_lib) if "compile" in name.lower() or "recomp" in name.lower()]
        log(f"MaterialEditingLibrary compile-like methods: {methods}")
        if recompile_material and hasattr(material_lib, "recompile_material"):
            log("Calling MaterialEditingLibrary.recompile_material()")
            material_lib.recompile_material(asset)

    log("Probe completed")


if __name__ == "__main__":
    main()

from fbx_inspector.ui.lod import parse_lod_name


def test_parse_lod_suffix() -> None:
    assert parse_lod_name("Tree_LOD0") == ("Tree", 0)
    assert parse_lod_name("|asset|Tree-lod12") == ("Tree", 12)


def test_plain_mesh_has_no_explicit_lod() -> None:
    assert parse_lod_name("Tree") is None
    assert parse_lod_name("Tree_LOD") is None

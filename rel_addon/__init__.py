import os
import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty
from bpy.types import Operator, Object
from . import r_rel, n_rel, c_rel


bl_info = {
    "name": "Export RELs (PSO)",
    "blender": (3, 4, 0),
    "category": "Export",
}


def filter_objects_by_props(props: list[str]) -> list[Object]:
    """Throws if an object has at least one prop but not all props"""
    objects = []
    for obj in bpy.data.objects:
        has = list(prop for prop in props if prop in obj)
        if len(has) > 0:
            hasnt = list(prop for prop in props if prop not in obj)
            if len(hasnt) > 0:
                raise Exception((
                    "Mesh \"{}\" is missing the following properties: {}, "
                    "which are required because it has the following properties: {}")
                        .format(obj.name, hasnt, has))
            objects.append(obj)
    return objects


class ExportRel(Operator, ExportHelper):
    """Export render geometry (n.rel), collision geometry (c.rel), and minimap geometry (r.rel)"""
    bl_idname = "export_scene.rel"
    bl_label = bl_info["name"]

    # ExportHelper mixin class uses this
    filename_ext = ".rel"

    filter_glob: StringProperty(
        # Suppress flake8 false errors
        default="*.rel", # noqa: F722
        options={"HIDDEN"}, # noqa: F821
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    filepath: StringProperty(subtype="FILE_PATH") # noqa: F821

    def cancel_with_error(self, ex: Exception()):
        self.report({"ERROR"}, str(ex))
        return {"CANCELLED"}

    def execute(self, context):
        try:
            minimap_objs = filter_objects_by_props(["rrel"])
            render_objs = filter_objects_by_props(["nrel"])
            collision_objs = filter_objects_by_props(["crel"])
        except Exception as ex:
            return self.cancel_with_error(ex)
        (noext, ext) = os.path.splitext(self.filepath)
        if len(minimap_objs) > 0:
            r_rel.write(noext + "r" + ext, minimap_objs)
        if len(render_objs) > 0:
            n_rel.write(noext + "n" + ext, render_objs)
        if len(collision_objs):
            c_rel.write(noext + "c" + ext, collision_objs)
        return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(ExportRel.bl_idname, text=bl_info["name"])


# Register and add to the "file selector" menu
def register():
    bpy.utils.register_class(ExportRel)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportRel)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

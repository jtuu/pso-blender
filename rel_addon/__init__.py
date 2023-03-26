import os
import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator, Object, Panel
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
        default="*.rel",
        options={"HIDDEN"},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    export_strategy: EnumProperty(
        name="Export",
        options={"ENUM_FLAG"},
        items=[
            ("EXPORT_BY_TAGS", "By tags", "Export all objects in the scene based on their tags", 1),
            ("EXPORT_SELECTED", "Selected only", "Only export selected objects as chosen format, ignoring their tags", 2)
        ],
        default={"EXPORT_BY_TAGS"}
    )

    export_as_format: EnumProperty(
        name="As format",
        items=[
            ("EXPORT_AS_NREL", "n.rel", "", 1),
            ("EXPORT_AS_NREL_XVM", "n.rel+xvm", "", 2),
            ("EXPORT_AS_CREL", "c.rel", "", 3),
            ("EXPORT_AS_RREL", "r.rel", "", 4),
            ("EXPORT_AS_ALL", "All", "", 5)
        ],
        default="EXPORT_AS_ALL"
    )

    filepath: StringProperty(subtype="FILE_PATH")

    def cancel_with_error(self, ex: Exception):
        self.report({"ERROR"}, str(ex))
        return {"CANCELLED"}
    
    def cancel_with_warning(self, msg: str):
        self.report({"WARNING"}, msg)
        return {"CANCELLED"}

    def export_selected(self):
        objs = bpy.context.selected_objects
        if len(objs) < 1:
            objs = bpy.context.collection.objects
        if len(objs) < 1:
            return self.cancel_with_warning("REL export error: No objects selected")
        noext, ext = os.path.splitext(self.filepath)
        format_info = {
            "EXPORT_AS_NREL": lambda: n_rel.write(self.filepath, None, objs),
            "EXPORT_AS_NREL_XVM": lambda: n_rel.write(self.filepath, noext + ".xvm", objs),
            "EXPORT_AS_CREL": lambda: c_rel.write(self.filepath, objs),
            "EXPORT_AS_RREL": lambda: r_rel.write(self.filepath, objs),
            "EXPORT_AS_ALL": lambda: self.export_all(objs, objs, objs)
        }
        writer = format_info[self.export_as_format]
        if self.export_as_format not in format_info:
            return self.cancel_with_warning("REL export error: Invalid export format")
        writer()
        return {"FINISHED"}
    
    def export_all(self, minimap_objs, render_objs, collision_objs):
        noext, ext = os.path.splitext(self.filepath)
        if minimap_objs and len(minimap_objs) > 0:
            r_rel.write(noext + "r" + ext, minimap_objs)
        if render_objs and len(render_objs) > 0:
            n_rel.write(noext + "n" + ext, noext + ".xvm", render_objs)
        if collision_objs and len(collision_objs):
            c_rel.write(noext + "c" + ext, collision_objs)
        return {"FINISHED"}
    
    def export_all_by_tags(self):
        try:
            minimap_objs = filter_objects_by_props(["rrel"])
            render_objs = filter_objects_by_props(["nrel"])
            collision_objs = filter_objects_by_props(["crel"])
        except Exception as ex:
            return self.cancel_with_error(ex)
        return self.export_all(minimap_objs, render_objs, collision_objs)

    def execute(self, context):
        if "EXPORT_SELECTED" in self.export_strategy:
            return self.export_selected()
        elif "EXPORT_BY_TAGS" in self.export_strategy:
            return self.export_all_by_tags()
        return self.cancel_with_warning("REL export error: Invalid export settings")
    
    def draw(self, context):
        pass


class CUSTOM_PT_export_settings(Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Settings Panel"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "EXPORT_SCENE_OT_rel"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        sfile = context.space_data
        operator = sfile.active_operator

        box = layout.box()
        box.row(align=True).prop(operator, "export_strategy")
        export_as_format_row = box.row(align=True)
        export_as_format_row.prop(operator, "export_as_format")
        export_as_format_row.enabled = "EXPORT_SELECTED" in operator.export_strategy
        if not export_as_format_row.enabled:
            operator.export_as_format = "EXPORT_AS_ALL"


def menu_func_export(self, context):
    self.layout.operator(ExportRel.bl_idname, text=bl_info["name"])


# Register and add to the "file selector" menu
def register():
    bpy.utils.register_class(ExportRel)
    bpy.utils.register_class(CUSTOM_PT_export_settings)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportRel)
    bpy.utils.unregister_class(CUSTOM_PT_export_settings)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

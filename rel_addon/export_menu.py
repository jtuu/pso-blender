import os
from warnings import catch_warnings
import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator, Panel
from . import r_rel, n_rel, c_rel


class ExportRel(Operator, ExportHelper):
    """Export render geometry (n.rel), collision geometry (c.rel), and minimap geometry (r.rel)"""
    bl_idname = "export_scene.rel"
    bl_label = "Export RELs (PSO)"

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
            "EXPORT_AS_NREL_XVM": lambda: n_rel.write(self.filepath, noext[0:-1] + ".xvm", objs, []),
            "EXPORT_AS_CREL": lambda: c_rel.write(self.filepath, objs),
            "EXPORT_AS_RREL": lambda: r_rel.write(self.filepath, objs),
            "EXPORT_AS_ALL": lambda: self.export_all(objs, objs, objs)
        }
        writer = format_info[self.export_as_format]
        if self.export_as_format not in format_info:
            return self.cancel_with_warning("REL export error: Invalid export format")
        writer()
        return {"FINISHED"}
    
    def export_all(self, minimap_objs, render_objs, collision_objs, chunk_markers):
        noext, ext = os.path.splitext(self.filepath)
        if minimap_objs and len(minimap_objs) > 0:
            r_rel.write(noext + "r" + ext, minimap_objs)
        if render_objs and len(render_objs) > 0:
            n_rel.write(noext + "n" + ext, noext + ".xvm", render_objs, chunk_markers)
        if collision_objs and len(collision_objs):
            c_rel.write(noext + "c" + ext, collision_objs)
        return {"FINISHED"}
    
    def export_all_by_tags(self):
        render_objs = []
        collision_objs = []
        minimap_objs = []
        chunk_markers = []
        for obj in bpy.data.objects:
            if obj.rel_settings.is_nrel:
                render_objs.append(obj)
            if obj.rel_settings.is_crel:
                collision_objs.append(obj)
            if obj.rel_settings.is_rrel:
                minimap_objs.append(obj)
            if obj.rel_settings.is_chunk:
                chunk_markers.append(obj)
        return self.export_all(minimap_objs, render_objs, collision_objs, chunk_markers)

    def execute(self, context):
        with catch_warnings(record=True) as warnings:
            result = {"CANCELLED"}
            if "EXPORT_SELECTED" in self.export_strategy:
                result = self.export_selected()
            elif "EXPORT_BY_TAGS" in self.export_strategy:
                result = self.export_all_by_tags()
            # Display warnings in the GUI
            for warning in warnings:
                self.report({"WARNING"}, str(warning.message))
            return result
    
    def draw(self, context):
        pass


class CUSTOM_PT_export_settings(Panel):
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_label = "Settings Panel"
    bl_options = {"HIDE_HEADER"}

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

import bpy
import os
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from . import xj


class ExportXj(Operator, ExportHelper):
    bl_idname = "export_scene.xj"
    bl_label = "Export xj"

    # ExportHelper mixin class uses this
    filename_ext = ".xj"

    filter_glob: StringProperty(
        default="*.xj",
        options={"HIDDEN"},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    filepath: StringProperty(subtype="FILE_PATH")

    def only_meshes(self, objs: list[bpy.types.Object]):
        return [obj for obj in objs if obj.type == "MESH"]

    def execute(self, context):
        noext, ext = os.path.splitext(self.filepath)
        # Try use selected if any
        objs = self.only_meshes(bpy.context.selected_objects)
        if len(objs) < 1:
            # otherwise just use the first object
            objs = self.only_meshes(bpy.data.objects)
        xj.write(self.filepath, noext + ".xvm", objs[0])
        return {"FINISHED"}
    
    def draw(self, context):
        pass

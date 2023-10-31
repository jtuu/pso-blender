import os
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from . import bml


class ExportBml(Operator, ExportHelper):
    bl_idname = "export_scene.bml"
    bl_label = "Export BML"

    # ExportHelper mixin class uses this
    filename_ext = ".bml"

    filter_glob: StringProperty(
        default="*.bml",
        options={"HIDDEN"},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        noext, ext = os.path.splitext(self.filepath)
        bml.write(self.filepath, noext + ".xvm")
        return {"FINISHED"}
    
    def draw(self, context):
        pass

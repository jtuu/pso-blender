import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from . import bml


class ImportBml(Operator, ImportHelper):
    bl_idname = "import_scene.bml"
    bl_label = "Import BML"

    filter_glob: StringProperty(
        default="*.bml",
        options={"HIDDEN"},
        maxlen=255,
    )

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        collection = bml.read(self.filepath)
        bpy.context.scene.collection.children.link(collection)
        return {"FINISHED"}

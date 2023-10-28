import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from . import xj


class ImportXj(Operator, ImportHelper):
    bl_idname = "import_scene.xj"
    bl_label = "Import XJ"

    filter_glob: StringProperty(
        default="*.xj",
        options={"HIDDEN"},
        maxlen=255,
    )

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        collections = xj.read(self.filepath)
        for coll in collections:
            bpy.context.scene.collection.children.link(coll)
        return {"FINISHED"}

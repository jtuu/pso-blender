import bpy, os
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from . import c_rel, n_rel


class ImportRel(Operator, ImportHelper):
    bl_idname = "import_scene.rel"
    bl_label = "Import REL"

    filter_glob: StringProperty(
        default="*n.rel;*c.rel;*r.rel",
        options={"HIDDEN"},
        maxlen=255,
    )

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        collection = None
        filename = os.path.basename(self.filepath)
        noext, ext = os.path.splitext(filename)
        suffix = noext[-1]

        if suffix == "c":
            collection = c_rel.read(self.filepath)
        elif suffix == "n":
            collection = n_rel.to_blender(filename, n_rel.read(self.filepath))
        elif suffix == "r":
            self.report({"ERROR"}, "Unimplemented file type for import")
        else:
            self.report({"ERROR"}, "Could not detect REL file type based on filename. Expected a filename ending in 'n.rel', 'c.rel', or 'r.rel'.")
        
        if collection is None:
            return {"CANCELLED"}

        bpy.context.scene.collection.children.link(collection)
        return {"FINISHED"}

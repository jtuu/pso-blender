import os, math
from mathutils import Vector
from dataclasses import dataclass
from warnings import warn
import bpy.types
from .rel import Rel
from .serialization import Serializable, Numeric, AlignedString
from . import util, xvm, xj
from .njcm import MeshTreeNode
from .njtl import TextureList, TextureListEntry


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


class MeshTreeFlag:
    NO_FOG = 0x1
    RECEIVES_SHADOWS = 0x10


@dataclass
class MeshTree(Serializable):
    root_node: Ptr32 = NULLPTR # MeshTreeNode
    unk1: U32 = 0
    unk2: U32 = 0
    tree_flags: U32 = 0


@dataclass
class Chunk(Serializable):
    """I think chunks might be used for view distance"""
    id: U32 = 0
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    rot_x: I32 = 0
    rot_y: I32 = 0
    rot_z: I32 = 0
    radius: F32 = 0.0
    static_mesh_trees: Ptr32 = NULLPTR # MeshTree
    animated_mesh_trees: Ptr32 = NULLPTR # Unknown
    static_mesh_tree_count: U32 = 0
    animated_mesh_tree_count: U32 = 0
    flags: U32 = 0

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return self.id == other.id


@dataclass
class NrelFmt2(Serializable):
    magic: list[U8] = util.magic_field("fmt2")
    unk1: U32 = 0
    chunk_count: U16 = 0
    unk2: U16 = 0
    radius: F32 = 0.0 # Overwritten at runtime
    chunks: Ptr32 = NULLPTR # Chunk
    texture_data: Ptr32 = NULLPTR # TextureList


class NrelError(Exception):
    def __init__(self, msg: str, *args, obj: bpy.types.Object=None, texture: bpy.types.Image=None):
        s = "N.REL Error"
        if obj:
            s += " in Object '{}'".format(obj.name)
        elif texture:
            s += " in Texture '{}'".format(texture.filepath)
        s += ": " + msg
        super().__init__(s)


def assign_objects_to_chunks(objects: list[bpy.types.Object], chunk_markers: list[bpy.types.Object]) -> dict[Chunk, list[bpy.types.Object]]:
    max_chunk_radius = 1200 # Approximation based on lowest value used by game
    chunk_to_children = dict()
    chunk_flags = 0x00010000
    chunk_counter = 0
    if len(chunk_markers) < 1:
        # No markers, put all meshes in the same chunk at 0,0,0
        warn("N.REL Warning: No chunk markers found in scene. Placing all meshes in default chunk.")
        chunk = Chunk(
            id=chunk_counter,
            flags=chunk_flags,
            static_mesh_tree_count=len(objects),
            x=0.0,
            y=0.0,
            z=0.0)
        chunk_to_children[chunk] = objects
    else:
        # Create a chunk for each marker
        for marker in chunk_markers:
            marker_center = util.from_blender_axes(marker.location)
            chunk = Chunk(
                id=chunk_counter,
                flags=chunk_flags,
                radius=float("-inf"),
                x=marker_center.x,
                y=0.0,
                z=marker_center.z)
            chunk_to_children[chunk] = []
            chunk_counter += 1
        # Find each object's nearest chunk
        for obj in objects:
            obj_center = util.from_blender_axes(util.geometry_world_center(obj))
            nearest_chunk = None
            nearest_dist_sq = float("inf")
            for chunk in chunk_to_children:
                dist_sq = util.distance_squared(obj_center.xz, Vector((chunk.x, 0.0, chunk.z)).xz)
                if dist_sq < nearest_dist_sq:
                    nearest_dist_sq = dist_sq
                    nearest_chunk = chunk
            # Add object to chunk
            chunk_to_children[nearest_chunk].append(obj)
            nearest_chunk.static_mesh_tree_count += 1
            # Also calculate chunk radius. Ensure object is definitely within radius by adding its greatest XZ dimension.
            greatest_obj_dim = max(obj.dimensions.xz)
            radius = math.sqrt(nearest_dist_sq) + greatest_obj_dim
            if radius > nearest_chunk.radius:
                nearest_chunk.radius = radius
                if radius > max_chunk_radius:
                    warn("N.REL Warning: Object '{}' might be too far away from a chunk marker (expected maximum distance of {:.1f}, was {:.1}).".format(
                        obj.name, max_chunk_radius, radius))
        # Discard empty chunks
        for chunk in list(chunk_to_children.keys()):
            if chunk.static_mesh_tree_count < 1:
                del chunk_to_children[chunk]
    return chunk_to_children


def write(nrel_path: str, xvm_path: str, objects: list[bpy.types.Object], chunk_markers: list[bpy.types.Object]):
    rel = Rel()
    nrel = NrelFmt2()
    textures = xvm.assign_texture_identifiers(objects)
    # Create chunks
    chunk_to_children = assign_objects_to_chunks(objects, chunk_markers)
    nrel.chunk_count = len(chunk_to_children)
    # Create chunk data.
    # Chunk coords are world, MeshNodes are local to chunks, mesh vertices are local to MeshNode
    for chunk in chunk_to_children:
        chunk_world_pos = Vector((chunk.x, chunk.y, chunk.z))
        chunk_objects = chunk_to_children[chunk]
        static_mesh_trees = []
        for obj in chunk_objects:
            blender_mesh = obj.to_mesh()
            if len(blender_mesh.loop_triangles) < 1:
                raise NrelError("Object has no faces.", obj=obj)
            # One mesh per tree. Create tree, a node, and the mesh.
            tree_flags = 0
            if not obj.rel_settings.receives_fog:
                tree_flags |= MeshTreeFlag.NO_FOG
            if obj.rel_settings.receives_shadows:
                tree_flags |= MeshTreeFlag.RECEIVES_SHADOWS
            static_mesh_tree = MeshTree(tree_flags=tree_flags)

            mesh_world_pos = util.from_blender_axes(obj.location)
            mesh_node = MeshTreeNode(
                eval_flags=xj.NinjaEvalFlag.UNIT_ANG | xj.NinjaEvalFlag.UNIT_SCL | xj.NinjaEvalFlag.BREAK,
                # Make coords relative to chunk
                x=mesh_world_pos.x - chunk_world_pos.x,
                y=mesh_world_pos.y - chunk_world_pos.y,
                z=mesh_world_pos.z - chunk_world_pos.z)
            mesh = xj.make_mesh(rel, obj, blender_mesh, textures)
            mesh_node.mesh = rel.write(mesh)
            static_mesh_tree.root_node = rel.write(mesh_node)
            static_mesh_trees.append(static_mesh_tree)
        # Write mesh trees back to back
        first_static_mesh_tree_ptr = NULLPTR
        for tree in static_mesh_trees:
            ptr = rel.write(tree)
            if first_static_mesh_tree_ptr == NULLPTR:
                first_static_mesh_tree_ptr = ptr
        chunk.static_mesh_trees = first_static_mesh_tree_ptr
    # Write chunks back to back
    first_chunk_ptr = NULLPTR
    for chunk in chunk_to_children:
        ptr = rel.write(chunk)
        if first_chunk_ptr == NULLPTR:
            first_chunk_ptr = ptr
    nrel.chunks = first_chunk_ptr
    # Texture metadata
    if len(textures) > 0:
        first_texlist_entry_ptr = NULLPTR
        texlist = TextureList(count=len(textures))
        for tex_path in textures:
            # There might be a limit on the length of these
            (dirname, basename) = os.path.split(tex_path)
            tex_name = basename[0:10]
            name_ptr = rel.write(AlignedString(tex_name, Rel.ALIGNMENT))
            ptr = rel.write(TextureListEntry(name=name_ptr))
            if first_texlist_entry_ptr == NULLPTR:
                first_texlist_entry_ptr = ptr
        texlist.elements = first_texlist_entry_ptr
        nrel.texture_data = rel.write(texlist)
    # Write files
    file_contents = rel.finish(rel.write(nrel))
    with open(nrel_path, "wb") as f:
        f.write(file_contents)
    if xvm_path and len(textures) > 0:
        xvm.write(xvm_path, list(textures.values()))

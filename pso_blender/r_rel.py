import math
from dataclasses import dataclass
import bpy.types
from .rel import Rel
from .serialization import Serializable, Numeric
from . import util, tristrip
from .nj import (
    Vertex,
    Mesh,
    VertexListNode,
    IndexArray,
    IndexListNode)


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


@dataclass
class MeshContainer(Serializable):
    unk1: U32 = 0
    mesh: Ptr32 = NULLPTR # Mesh


@dataclass
class Room(Serializable):
    id: U16 = 0
    flags: U16 = 0
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    rot_x: I32 = 0
    rot_y: I32 = 0
    rot_z: I32 = 0
    color_alpha: F32 = 0.0
    discovery_radius: F32 = 0.0
    mesh_container: Ptr32 = NULLPTR # MeshContainer


@dataclass
class Minimap(Serializable):
    rooms: Ptr32 = NULLPTR # Room
    unk1: U32 = 0 # Maybe textures
    room_count: U32 = 0
    unk2: U32 = 0


def write(path: str, room_objects: list[bpy.types.Object]):
    rel = Rel()
    minimap = Minimap()
    minimap.room_count = len(room_objects)
    rooms = []
    for (i, obj) in enumerate(room_objects):
        blender_mesh = obj.to_mesh()

        geom_center = util.from_blender_axes(util.geometry_world_center(obj)) * util.get_pso_world_scale()
        room = Room(
            id=i,
            flags=1,
            x=geom_center[0],
            y=geom_center[1],
            z=geom_center[2])

        faces = util.mesh_faces(blender_mesh)
        vertices = []
        farthest_sq = float("-inf")
        for local_vert in blender_mesh.vertices:
            # Apply transforms from object but translate position back to local
            world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co) * util.get_pso_world_scale() - geom_center
            farthest_sq = max(farthest_sq, util.distance_squared(geom_center, world_vert))
            vertices.append(Vertex(
                x=world_vert[0], y=world_vert[1], z=world_vert[2],
                nx=0.0, ny=1.0, nz=0.0))
        room.discovery_radius = math.sqrt(farthest_sq)
        strips = tristrip.stripify(faces, stitchstrips=True)

        container = MeshContainer()
        mesh = Mesh(
            x=geom_center[0],
            y=geom_center[1],
            z=geom_center[2])

        vertex_node = VertexListNode(
            flags=0x29,
            offset_to_next=Vertex.type_size() * len(vertices) // 4 + 1,
            vertex_count=len(vertices),
            vertices=vertices)
        vertex_node_ptr = rel.write(vertex_node)
        rel.write(VertexListNode(flags=0xff)) # Terminator

        # Indices
        indices = []
        indices_size = 0
        for strip in strips:
            indices.append(IndexArray(length=len(strip), indices=strip))
            indices_size += 2
            indices_size += len(strip) * 2

        index_node = IndexListNode(
                flags=0x0340,
                offset_to_next=indices_size // 2 + 1,
                strip_count=len(strips),
                indices=indices)

        # Due to variable amount of 16bit values we need to ensure alignment
        padding = None
        if (rel.buf.offset + IndexListNode.type_size() + indices_size) % 4 != 0:
            index_node.offset_to_next += 1
            padding = Numeric.endianness_prefix + "H"

        index_node_ptr = rel.write(index_node)

        if padding:
            rel.buf.pack(padding, 0)

        rel.write(IndexListNode(flags=0xff)) # Terminator

        mesh.vertex_list = vertex_node_ptr
        mesh.index_list = index_node_ptr
        mesh_ptr = rel.write(mesh)

        container.mesh = mesh_ptr
        container_ptr = rel.write(container)

        room.mesh_container = container_ptr
        rooms.append(room)

        obj.to_mesh_clear() # Delete temporary mesh
    # Write rooms
    first_room_ptr = None
    for room in rooms:
        room_ptr = rel.write(room)
        if first_room_ptr is None:
            first_room_ptr = room_ptr
    minimap.rooms = first_room_ptr
    minimap_ptr = rel.write(minimap)
    file_contents = rel.finish(minimap_ptr)
    with open(path, "wb") as f:
        f.write(file_contents)

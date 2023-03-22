from dataclasses import dataclass, field
from bpy.types import Mesh
from .rel import Rel
from .serialization import Serializable, Numeric
from . import util, triangle_strip


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr16 = Numeric.Ptr16
Ptr32 = Numeric.Ptr32


@dataclass
class Vertex(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    nx: F32 = 0.0
    ny: F32 = 0.0
    nz: F32 = 0.0


@dataclass
class VertexListNode(Serializable):
    flags: U16 = 0 # 0xff=terminator
    # Offset to next VertexListNode, BUT divided by four
    offset_to_next: U16 = 0
    unk1: U16 = 0
    vertex_count: U16 = 0
    vertices: list[Vertex] = field(default_factory=list)


@dataclass
class IndexListNode(Serializable):
    flags: U16 = 0
    # Offset to next IndexListNode, BUT divided by two
    offset_to_next: U16 = 0
    strip_count: U16 = 0
    indices: list[U16] = field(default_factory=list)


@dataclass
class VertexContainer2(Serializable):
    vertex_list: Ptr16 = 0
    index_list: Ptr16 = 0


# Dunno what the point of this extra level of indirection is.
# Maybe to have more than one mesh per room?
@dataclass
class VertexContainer1(Serializable):
    unk1: U32 = 0
    vertex_container2: Ptr16 = 0


@dataclass
class Room(Serializable):
    id: U32 = 0
    flags: U16 = 0
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    rot_x: I32 = 0
    rot_y: I32 = 0
    rot_z: I32 = 0
    color_alpha: F32 = 0.0
    discovery_radius: F32 = 0.0
    vertex_container1: Ptr16 = 0


@dataclass
class Minimap(Serializable):
    rooms: Ptr16 = 0
    unk1: U32 = 0
    room_count: U32 = 0
    unk2: U32 = 0


def write(path: str, rooms: list[Mesh]):
    rel = Rel()
    minimap = Minimap()
    minimap.room_count = len(rooms)
    first_room_ptr = None
    for (i, mesh) in enumerate(rooms):
        room = Room(id=i, discovery_radius=1000.0, flags=1)

        faces = util.mesh_faces(mesh)
        vertices = list(Vertex(x=v.co[0], y=v.co[1], z=v.co[2], nx=0.0, ny=1.0, nz=0.0) for v in mesh.vertices)
        indices = triangle_strip.find_strip(faces)

        container1 = VertexContainer1()
        container2 = VertexContainer2()

        vertex_node = VertexListNode(
            flags=0x29,
            offset_to_next=Vertex.size() * len(vertices) // 4 + 1,
            vertex_count=len(vertices),
            vertices=vertices)
        vertex_list_terminator = VertexListNode(flags=0xff)

        index_node = IndexListNode(
            flags=0x0340,
            offset_to_next=2 * len(indices) // 2 + 1,
            strip_count=1,
            indices=indices)
        index_list_terminator = IndexListNode(flags=0xff)

        vertex_node_ptr = rel.write(vertex_node)
        rel.write(vertex_list_terminator)

        index_node_ptr = rel.write(index_node)
        rel.write(index_list_terminator)

        container2.vertex_list = vertex_node_ptr
        container2.index_list = index_node_ptr
        container2_ptr = rel.write(container2)

        container1.vertex_container2 = container2_ptr
        container1_ptr = rel.write(container1)

        room.vertex_container1 = container1_ptr
        room_ptr = rel.write(room)
        if first_room_ptr is None:
            first_room_ptr = room_ptr
    minimap.rooms = first_room_ptr
    minimap_ptr = rel.write(minimap)
    file_contents = rel.finish(minimap_ptr)
    with open(path, "wb") as f:
        f.write(file_contents)


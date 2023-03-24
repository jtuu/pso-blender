from dataclasses import dataclass, field
from bpy.types import Mesh
from .rel import Rel
from .serialization import Serializable, Numeric
from . import util


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
class IndexArray(Serializable):
    length: U16 = 0
    indices: list[U16] = field(default_factory=list)


@dataclass
class IndexListNode(Serializable):
    flags: U16 = 0
    # Offset to next IndexListNode, BUT divided by two
    offset_to_next: U16 = 0
    strip_count: U16 = 0
    indices: list[IndexArray] = field(default_factory=lambda: [IndexArray(length=0)])


@dataclass
class VertexContainer2(Serializable):
    vertex_list: Ptr32 = NULLPTR
    index_list: Ptr32 = NULLPTR
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0


# Dunno what the point of this extra level of indirection is.
# Maybe to have more than one mesh per room?
@dataclass
class VertexContainer1(Serializable):
    unk1: U32 = 0
    vertex_container2: Ptr32 = NULLPTR


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
    vertex_container1: Ptr32 = NULLPTR


@dataclass
class Minimap(Serializable):
    rooms: Ptr32 = NULLPTR
    unk1: U32 = 0
    room_count: U32 = 0
    unk2: U32 = 0


def write(path: str, room_meshes: list[Mesh]):
    rel = Rel()
    minimap = Minimap()
    minimap.room_count = len(room_meshes)
    rooms = []
    for (i, mesh) in enumerate(room_meshes):
        room = Room(id=i, discovery_radius=1000.0, flags=1)

        faces = util.mesh_faces(mesh)
        vertices = []
        for v in mesh.vertices:
            # Swap y and z because blender has them swapped
            vertices.append(Vertex(x=v.co[0], y=v.co[2], z=v.co[1], nx=0.0, ny=1.0, nz=0.0))
        strips = util.stripify(faces)

        container1 = VertexContainer1()
        container2 = VertexContainer2()

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
            padding = "<H"

        index_node_ptr = rel.write(index_node)

        if padding:
            rel.buf.pack(padding, 0)

        rel.write(IndexListNode(flags=0xff)) # Terminator

        container2.vertex_list = vertex_node_ptr
        container2.index_list = index_node_ptr
        container2_ptr = rel.write(container2)

        container1.vertex_container2 = container2_ptr
        container1_ptr = rel.write(container1)

        room.vertex_container1 = container1_ptr
        rooms.append(room)
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

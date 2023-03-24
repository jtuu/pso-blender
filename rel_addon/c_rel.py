from dataclasses import dataclass, field
import bpy.types 
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


@dataclass
class VertexArray(Serializable):
    vertices: list[Vertex] = field(default_factory=list)


@dataclass
class Face(Serializable):
    index0: U16 = 0
    index1: U16 = 0
    index2: U16 = 0
    flags: U16 = 0
    nx: F32 = 0.0
    ny: F32 = 0.0
    nz: F32 = 0.0
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    radius: F32 = 0.0


@dataclass
class Mesh(Serializable):
    unk1: U32 = 0
    vertices: Ptr32 = NULLPTR
    face_count: U32 = 0
    faces: Ptr32 = NULLPTR


@dataclass
class CrelNode(Serializable):
    mesh: Ptr32 = NULLPTR
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    radius: F32 = 0.0
    flags: U32 = 0


@dataclass
class Crel(Serializable):
    nodes: Ptr32 = NULLPTR


def write(path: str, meshes: list[bpy.types.Mesh]):
    rel = Rel()
    nodes = []
    for blender_mesh in meshes:
        node = CrelNode(flags=0x00000921, radius=300.0)

        vertex_array = VertexArray()
        for v in blender_mesh.vertices:
            # Swap y and z
            vertex_array.vertices.append(Vertex(x=v.co[0], y=v.co[2], z=v.co[1]))

        faces = util.mesh_faces(blender_mesh)
        mesh = Mesh(vertices=rel.write(vertex_array), face_count=len(faces))

        # Write faces
        first_face_ptr = None
        for face in faces:
            ptr = rel.write(Face(
                flags=0x0101,
                # Reverse winding for some reason
                index0=face[2], index1=face[1], index2=face[0],
                radius=300.0,
                ny=1.0))
            if first_face_ptr is None:
                first_face_ptr = ptr
        mesh.faces = first_face_ptr

        node.mesh = rel.write(mesh)
        nodes.append(node)
    nodes.append(CrelNode()) # Terminator
    # Write nodes
    first_node_ptr = None
    for node in nodes:
        ptr = rel.write(node)
        if first_node_ptr is None:
            first_node_ptr = ptr
    file_contents = rel.finish(rel.write(Crel(nodes=first_node_ptr)))
    with open(path, "wb") as f:
        f.write(file_contents)

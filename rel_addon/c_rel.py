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
    vertices: Ptr32 = NULLPTR # VertexArray
    face_count: U32 = 0
    faces: Ptr32 = NULLPTR # Face


@dataclass
class CrelNode(Serializable):
    mesh: Ptr32 = NULLPTR # Mesh
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    radius: F32 = 0.0
    flags: U32 = 0


@dataclass
class Crel(Serializable):
    nodes: Ptr32 = NULLPTR # CrelNode


def write(path: str, objects: list[bpy.types.Object]):
    rel = Rel()
    nodes = []
    for obj in objects:
        blender_mesh = obj.to_mesh()
        node = CrelNode(flags=0x00000921, radius=3000.0)

        vertex_array = VertexArray()
        for local_vert in blender_mesh.vertices:
            world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co)
            vertex_array.vertices.append(Vertex(
                x=world_vert[0], y=world_vert[1], z=world_vert[2]))

        mesh = Mesh(vertices=rel.write(vertex_array), face_count=len(blender_mesh.loop_triangles))

        # Write faces
        first_face_ptr = None
        for face in blender_mesh.loop_triangles:
            rface = face.vertices
            normal = util.from_blender_axes(face.normal)
            ptr = rel.write(Face(
                flags=0x0101,
                index0=rface[0],
                index1=rface[1],
                index2=rface[2],
                radius=300.0,
                nx=normal[0],
                ny=normal[1],
                nz=normal[2]))
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

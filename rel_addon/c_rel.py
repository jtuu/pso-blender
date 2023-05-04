import math, os
from mathutils import Vector
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

    def __iter__(self):
        return iter([self.x, self.y, self.z])

    def as_vector(self) -> Vector:
        return Vector((self.x, self.y, self.z))


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
    vertex_count: U32 = 0
    vertices: Ptr32 = NULLPTR # VertexArray
    face_count: U32 = 0
    faces: Ptr32 = NULLPTR # Face


COLLISION_FLAG_NAMES = {
    0x1: "Camera",
    0x2: "Unknown",
    0x4: "Water terrain",
    0x8: "Unknown",
    0x10: "Grass terrain",
    0x20: "Wall",
    0x40: "Monsters only", # Allows monsters to aggro and path towards it but prevents actually going through it
    0x80: "Unknown",
    0x100: "Projectiles",
    0x200: "Unknown",
    0x400: "Unknown",
    0x800: "Players and monsters", # Prevents players. Allows monsters to aggro but not path towards it or go through. 
    0x1000: "Unknown",
    0x2000: "Players only",
    0x4000: "Unknown",
    0x8000: "Monster vision", # Prevents monsters from seeing player
}


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
        vertex_array = VertexArray()
        geom_center = util.from_blender_axes(util.geometry_world_center(obj))

        collision_flags = obj.rel_settings.collision_flags_value1 | (obj.rel_settings.collision_flags_value2 << 16)

        node = CrelNode(
            flags=collision_flags,
            x=geom_center[0],
            y=geom_center[1],
            z=geom_center[2])
        farthest_sq = float("-inf")
        # Get vertices and find farthest vertex
        for local_vert in blender_mesh.vertices:
            world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co)
            farthest_sq = max(farthest_sq, util.distance_squared(geom_center.xz, world_vert.xz))
            vertex_array.vertices.append(Vertex(
                x=world_vert[0], y=world_vert[1], z=world_vert[2]))
        node.radius = math.sqrt(farthest_sq)

        mesh = Mesh(
            vertex_count=len(vertex_array.vertices),
            vertices=rel.write(vertex_array),
            face_count=len(blender_mesh.loop_triangles))

        # Write faces
        first_face_ptr = None
        for face in blender_mesh.loop_triangles:
            # Apply world rotation and scale transforms to normal
            normal = face.normal.to_4d()
            normal.w = 0
            normal = util.from_blender_axes((obj.matrix_world @ normal).to_3d().normalized())
            indices = face.vertices
            # Find farthest distance between vertices
            farthest_sq = float("-inf")
            for i in range(len(face.vertices)):
                for j in range(len(face.vertices)):
                    if i == j:
                        continue
                    a = vertex_array.vertices[i].as_vector().xz
                    b = vertex_array.vertices[j].as_vector().xz
                    farthest_sq = max(farthest_sq, util.distance_squared(a, b))
            center = util.from_blender_axes(obj.matrix_world @ face.center)
            radius = math.sqrt(farthest_sq)
            ptr = rel.write(Face(
                flags=collision_flags,
                x=center[0],
                y=center[1],
                z=center[2],
                index0=indices[0],
                index1=indices[1],
                index2=indices[2],
                radius=radius,
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


def flags_to_color(flags: int) -> tuple[float, float, float]:
    import colorsys
    flags = (flags * 1103515245 + 12345) % (1 << 31)
    return colorsys.hsv_to_rgb(flags / (1 << 31), 0.5, 0.5)


def to_blender_mesh(rel: Rel, node: CrelNode, node_idx: int) -> bpy.types.Object:
    blender_vertices = []
    blender_edges = []
    blender_faces = []
    (mesh, _) = rel.read(Mesh, node.mesh)
    blender_mesh = bpy.data.meshes.new("mesh_" + str(node_idx))
    faces = []

    vertex_size = Vertex.type_size()
    for i in range(mesh.vertex_count):
        (vertex, _) = rel.read(Vertex, mesh.vertices + vertex_size * i)
        coords = [vertex.x - node.x, vertex.z - node.z, vertex.y - node.y]
        blender_vertices.append(coords)

    face_size = Face.type_size()
    for i in range(mesh.face_count):
        (face, _) = rel.read(Face, mesh.faces + face_size * i)
        indices = [face.index0, face.index1, face.index2]
        blender_faces.append(indices)
        faces.append(face)

    blender_mesh.from_pydata(blender_vertices, blender_edges, blender_faces)
    blender_mesh.update()

    face_colors = blender_mesh.attributes.new("collision_type_color", "BYTE_COLOR", "CORNER")
    for (face_idx, poly) in enumerate(blender_mesh.polygons):
        for loop_idx in poly.loop_indices:
            color = flags_to_color(faces[face_idx].flags)
            out = face_colors.data[loop_idx].color
            out[0] = color[0]
            out[1] = color[1]
            out[2] = color[2]
            out[3] = 1.0

    obj = bpy.data.objects.new("object_" + str(node_idx), blender_mesh)
    obj.rel_settings.collision_flags_value1 = node.flags & 0xffff
    obj.rel_settings.collision_flags_value2 = (node.flags >> 16) & 0xffff

    flag_face_maps = dict()
    for (face_idx, face) in enumerate(faces):
        name = "collision_type_" + hex(face.flags)
        if name in flag_face_maps:
            grp = flag_face_maps[name]
        else:
            grp = obj.face_maps.new(name=name)
            flag_face_maps[name] = grp
        grp.add([face_idx])
    
    obj.location.x = node.x
    obj.location.y = node.z
    obj.location.z = node.y

    return obj


def read(path: str) -> bpy.types.Collection:
    filename = os.path.basename(path)
    collection = bpy.data.collections.new(filename)

    with open(path, "rb") as f:
        rel = Rel.read_from(bytearray(f.read()))
    (crel, _) = rel.read(Crel, rel.payload_offset)

    node_idx = 0
    node_offset = crel.nodes
    while True:
        (node, next_offset) = rel.read(CrelNode, node_offset)
        if not rel.is_nonnull_pointer(next_offset + 0):
            break
        obj = to_blender_mesh(rel, node, node_idx)
        collection.objects.link(obj)
        node_offset = next_offset
        node_idx += 1

    return collection



import bpy.types 
from dataclasses import field
from .trianglestripifier import TriangleStripifier
from . import trianglemesh


def mesh_faces(mesh: bpy.types.Mesh) -> list[tuple[int, int, int]]:
    """Returns vertex indices of triangulated faces"""
    faces = []
    for tri in mesh.loop_triangles:
        faces.append(tuple(tri.vertices))
    return faces


def get_object_diffuse_texture(obj: bpy.types.Object) -> bpy.types.Image:
    """Assumes the first image node is the correct one"""
    for mat_slot in obj.material_slots:
        if not mat_slot.material or not mat_slot.material.node_tree:
            continue
        for node in mat_slot.material.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                return node.image
    return None


def stripify(triangles):
    # Convert to pyffi Mesh
    mesh = trianglemesh.Mesh()
    for face in triangles:
        try:
            mesh.add_face(*face)
        except ValueError:
            # degenerate face
            pass
    mesh.lock()

    # Compute strips
    stripifier = TriangleStripifier(mesh)
    return stripifier.find_all_strips()


def magic_bytes(s: str) -> list[int]:
    return list(map(ord, s))


def magic_field(s: str):
    return field(default_factory=lambda: magic_bytes(s))


def from_blender_axes(tup, invert_z=True):
    """Swaps second and third component"""
    x, z, y = tup
    if invert_z:
        z *= -1
    return (x, y, z)

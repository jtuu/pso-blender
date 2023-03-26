from bpy.types import Mesh
from dataclasses import field
from .trianglestripifier import TriangleStripifier
from . import trianglemesh


def mesh_faces(mesh: Mesh) -> list[tuple[int, int, int]]:
    """Returns vertex indices of triangulated faces"""
    faces = []
    for tri in mesh.loop_triangles:
        faces.append(tuple(tri.vertices))
    return faces


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

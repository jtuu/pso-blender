import bpy
from dataclasses import dataclass, field
from .serialization import Serializable, Numeric, ResizableBuffer
from .xvm import TextureManager


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


class FrameType:
    UNKNOWN = 1
    SLIDESHOW = 2
    TERMINATOR = 0xffff


@dataclass
class Keyframe(Serializable):
    texture_index: U16 = 0
    frame_delay: U16 = 0


# .tam files are big endian on blue burst.....
@dataclass
class TamEntry(Serializable):
    frame_type: U16 = 0
    body_size: U16 = 0
    animation_id: U16 = 0
    frame_count: U16 = 0
    frames: list[Keyframe] = field(default_factory=list)


def write(tam_path: str, texture_man: TextureManager, objs: list[bpy.types.Object]):
    Numeric.use_big_endian()

    tam = ResizableBuffer(0)

    for obj in objs:
        anim_tex = texture_man.get_object_animated_texture(obj)
        if not anim_tex or anim_tex.animation_frames < 1:
            continue

        frames = []
        for i in range(anim_tex.animation_frames):
            # Assume frames are back to back in the texture archive
            frames.append(Keyframe(texture_index=anim_tex.id - texture_man.get_base_id() + i, frame_delay=1))

        entry = TamEntry(
            frame_type=FrameType.SLIDESHOW,
            body_size=Keyframe.type_size() * len(frames) + 4,
            animation_id=anim_tex.id & 0xffff,
            frame_count=len(frames),
            frames=frames)
        
        entry.serialize_into(tam)

    TamEntry(frame_type=FrameType.TERMINATOR).serialize_into(tam)

    with open(tam_path, "wb") as f:
        f.write(tam.buffer)

    Numeric.use_little_endian()

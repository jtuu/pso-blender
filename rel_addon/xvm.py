from dataclasses import dataclass, field
import bpy
import bpy.types
from .serialization import Serializable, Numeric, ResizableBuffer
from . import util, dxt


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
class Xvr(Serializable):
    magic: list[U8] = util.magic_field("XVRT")
    body_size: U32 = 0
    format1: U32 = 0
    format2: U32 = 0
    id: U32 = 0
    width: U16 = 0
    height: U16 = 0
    data_size: U32 = 0
    unk1: U32 = 0
    unk2: U32 = 0
    unk3: U32 = 0
    unk4: U32 = 0
    unk5: U32 = 0
    unk6: U32 = 0
    unk7: U32 = 0
    unk8: U32 = 0
    unk9: U32 = 0
    data: list[U8] = field(default_factory=list)


@dataclass
class Xvm(Serializable):
    magic: list[U8] = util.magic_field("XVMH")
    body_size: U32 = 0
    xvr_count: U32 = 0
    xvrs: list[Xvr] = field(default_factory=list)


@dataclass
class Texture:
    id: int
    image: bpy.types.Image


def write(path: str, textures: list[Texture]):
    xvrs = []
    for tex in textures:
        width, height = tex.image.size
        data = dxt.dxt1_compress(list(tex.image.pixels), width, height, tex.image.channels)
        xvrs.append(Xvr(
            body_size=len(data) + Xvr.type_size() - 4,
            id=tex.id,
            format1=0,
            format2=6,
            width=width,
            height=height,
            data_size=len(data),
            data=data))
    buf = ResizableBuffer(0)
    # I'll just explicitly write the lists because it's easier
    xvm = Xvm(
        body_size=Xvm.type_size() - 4,
        xvr_count=len(xvrs))
    xvm.serialize_into(buf)
    for xvr in xvrs:
        data = xvr.data
        xvr.data = []
        xvr.serialize_into(buf)
        buf.append(data)
        buf.seek_to_end()
    with open(path, "wb") as f:
        f.write(buf.buffer)

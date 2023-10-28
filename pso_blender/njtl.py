from dataclasses import dataclass
from .serialization import Serializable, Numeric


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
class TextureListEntry(Serializable):
    name: Ptr32 = NULLPTR # AlignedString
    unk1: Ptr32 = NULLPTR # Set at runtime
    data: Ptr32 = NULLPTR # Set at runtime


@dataclass
class TextureList(Serializable):
    elements: Ptr32 = NULLPTR # TextureListEntry
    count: U32 = 0

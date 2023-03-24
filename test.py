from dataclasses import dataclass, field
import unittest
from rel_addon.serialization import Serializable, Numeric, ResizableBuffer


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
class MyBasicStruct(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0


@dataclass
class MyFlexStruct(Serializable):
    flags: U32 = 0
    vertices: list[MyBasicStruct] = field(default_factory=list)


@dataclass
class MyUnalignedStruct(Serializable):
    foo: U16 = 0
    bar: U16 = 0
    buz: U16 = 0


@dataclass
class MyPointingStruct(Serializable):
    data_count: U32 = 0
    data: list[U8] = field(default_factory=list)
    child: Ptr32 = NULLPTR
    sibling: Ptr32 = NULLPTR


class TestSerialization(unittest.TestCase):
    def test_basic_struct_instance_size(self):
        self.assertEqual(MyBasicStruct().instance_size(), 12)
    
    def test_basic_struct_type_size(self):
        self.assertEqual(MyBasicStruct.type_size(), 12)
    
    def test_flex_struct_instance_size(self):
        vertices = [MyBasicStruct(), MyBasicStruct()]
        self.assertEqual(MyFlexStruct(vertices=vertices).instance_size(), 4 + 12 * 2)
    
    def test_flex_struct_type_size(self):
        self.assertEqual(MyFlexStruct.type_size(), 4)

    def test_resizable_buffer_pack(self):
        buf = ResizableBuffer(0)
        fmt = Numeric.format_of_type(U32)
        size = Numeric.size_of_format(fmt)
        buf.pack(fmt, 123)
        self.assertEqual(buf.capacity, size)
        self.assertEqual(buf.offset, size)
    
    def test_serialize_basic_struct_unaligned(self):
        buf = ResizableBuffer(0)
        item = MyUnalignedStruct()
        item.serialize_into(buf)
        self.assertEqual(buf.offset, 6)
    
    def test_serialize_basic_struct_aligned(self):
        buf = ResizableBuffer(0)
        item = MyUnalignedStruct()
        item.serialize_into(buf, 4)
        self.assertEqual(buf.offset, 8)

    def test_struct_nonnull_pointer_member_offsets(self):
        data = [1, 2, 3]
        item = MyPointingStruct(data_count=len(data), data=data, sibling=1337)
        self.assertEqual(item.nonnull_pointer_member_offsets(), [11])


if __name__ == '__main__':
    unittest.main()

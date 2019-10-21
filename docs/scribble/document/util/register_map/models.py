from __future__ import annotations

from dataclasses import dataclass
import enum
import typing as t


@dataclass(frozen=True)
class BitFieldRange:
    begin: int
    end: int  # Exclusive

    def as_verilog_range(self) -> str:
        """Return range as a Verilog range, e.g. [31:6].

        If range is just a single bit, then just return a single integer with
        no symbols.

        Note that although the range in modeled in Python as a semi-open
        interval, Verilog uses inclusive ranges.

        >>> BitFieldRange(0, 1).as_verilog_range()
        '0'

        >>> BitFieldRange(10, 20).as_verilog_range()
        '[19:10]'

        >>> BitFieldRange(10, 10).as_verilog_range()
        Traceback (most recent call last):
        ...
        ValueError: Invalid bit field range: [10, 10)

        >>> BitFieldRange(10, 9).as_verilog_range()
        Traceback (most recent call last):
        ...
        ValueError: Invalid bit field range: [10, 9)
        """
        if self.end <= self.begin:
            raise ValueError(f"Invalid bit field range: [{self.begin}, {self.end})")
        elif self.end == self.begin + 1:
            return str(self.begin)
        else:
            return f"[{self.end - 1}:{self.begin}]"


@dataclass(frozen=True)
class RegisterField:
    class Attr(enum.Enum):
        RW = "RW"  # Read and writable
        RO = "RO"  # Read-only
        WO = "WO"  # Write-only

    bits: BitFieldRange
    name: str  # The field's code name
    attr: Attr
    reset: t.Optional[int]  # If set, the value of the register after reset
    description: str  # A short, human-readable description

    _RESERVED = "reserved"

    @classmethod
    def reserved(cls, bits: BitFieldRange) -> "RegisterField":
        return cls(bits, name=cls._RESERVED, attr=RegisterField.Attr.RO, reset=0, description="")

    def is_reserved(self) -> bool:
        return self.name == self._RESERVED


@dataclass(frozen=True)
class Register:
    byte_offset: int
    name: str  # The register's code name
    description: str  # A short, human-readable description
    fields: t.List[RegisterField]  # Should be sorted

    _RESERVED = "reserved"

    def get_field(self, name: str) -> RegisterField:
        [field] = [field for field in self.fields if field.name == name]
        return field

    def is_reserved(self) -> bool:
        return self.name == self._RESERVED

    @property
    def byte_range(self) -> t.Tuple[int, int]:
        """Return the half-open interval of the low and high byte offsets."""
        lowest_bit_offset = self.fields[0].bits.begin
        highest_bit_offset = self.fields[-1].bits.end
        return (
            self.byte_offset + lowest_bit_offset // 8,
            self.byte_offset + highest_bit_offset // 8,
        )


@dataclass(frozen=True)
class RegisterMap:
    registers: t.List[Register]

    @classmethod
    def from_object_model(cls, register_map_object_model: dict) -> "RegisterMap":
        from .converter import load_register_map_from_object_model

        return load_register_map_from_object_model(register_map_object_model)

    def get_register(self, name: str) -> Register:
        try:
            [reg] = [reg for reg in self.registers if reg.name == name]
        except ValueError:
            raise ValueError(f"Could not find register {name}")
        return reg

    def get_register_field_table(self, name: str, reference_id: str):
        from .tables import get_register_field_table

        return get_register_field_table(register=self.get_register(name), reference_id=reference_id)

    def get_register_map_table(self, caption: str, reference_id: str):
        from .tables import get_register_map_table

        return get_register_map_table(register_map=self, caption=caption, reference_id=reference_id)

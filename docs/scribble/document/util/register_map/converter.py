from __future__ import annotations

import itertools
import typing as t

from intervaltree import Interval
from intervaltree import IntervalTree

from scribble.model import Element
from .models import BitFieldRange, Register, RegisterField, RegisterMap


# Reserved fields from the object model have this field name.
_OBJECT_MODEL_RESERVED_FIELD = "reserved"


T = t.TypeVar("T")
U = t.TypeVar("U")


def sorted_groupby(
    sequence: t.Sequence[T], key=t.Callable[[T], U]
) -> t.List[t.Tuple[U, t.List[T]]]:
    return [
        (group, list(items))
        for group, items in itertools.groupby(sorted(sequence, key=key), key=key)
    ]


def _get_group(field: t.Mapping) -> str:
    # Not all register fields have explicit groups, so default to the field's
    # name.
    description = field["description"]
    return description.get("group", description["name"])


def _get_uncovered_intervals(domain: Interval, covered_intervals: IntervalTree) -> IntervalTree:
    """
    Given an interval domain and a collection of intervals, return a list of
    uncovered intervals.
    """
    tree = IntervalTree([domain])
    for covered in covered_intervals:
        tree.chop(covered.begin, covered.end)
    return tree


def _fill_reserved_fields(fields: t.Sequence[Element], max_bit_offset: int) -> t.Sequence[Element]:
    domain = Interval(0, max_bit_offset)
    field_intervals = IntervalTree.from_tuples(
        [(field.bits.begin, field.bits.end) for field in fields]
    )
    gaps = _get_uncovered_intervals(domain=domain, covered_intervals=field_intervals)
    reserved_fields = [
        RegisterField.reserved(BitFieldRange(begin=gap.begin, end=gap.end)) for gap in gaps
    ]
    return fields + reserved_fields


def _create_register(
    group_name: str, group: t.Optional[Element], fields: t.Sequence[Element]
) -> Register:
    """
    Given a group of fields, create a register.

    The register size will be set to the nearest power of 2 that can contain
    it. The register should have a base address that is naturally aligned to
    its size; i.e. the base address should be evenly divisible by the size.
    """
    # Offset is relative to the base of the entire memory region.
    min_bit_offset = min([field["bitRange"]["base"] for field in fields])
    if min_bit_offset % 8 != 0:
        raise ValueError(f"Expected register to be byte-aligned: {group_name}")

    new_fields = [
        _convert_register_field(field, min_bit_offset=min_bit_offset)
        for field in fields
        if field["description"]["name"] != _OBJECT_MODEL_RESERVED_FIELD
    ]
    # Offset relative to the base of the register (i.e. min_bit_offset)
    max_bit_offset = max(field.bits.end for field in new_fields)  # Exclusive interval end
    # The register size is the smallest power of 2 that can contain all fields.
    register_size = max(2 ** (max_bit_offset - 1).bit_length(), 8)
    if min_bit_offset % register_size != 0:
        raise ValueError(
            f"Register {group_name} is misaligned: "
            f"base offset {min_bit_offset}, size {register_size}"
        )

    # Get description from description if available. Fallback to field
    # description if there is only one field.
    if group:
        description = group["description"]
    elif len(new_fields) == 1:
        [sole_field] = new_fields
        description = sole_field.description
    else:
        description = ""

    filled_fields = _fill_reserved_fields(new_fields, register_size)

    return Register(
        byte_offset=min_bit_offset // 8,
        name=group_name,
        description=description,
        fields=sorted(filled_fields, key=lambda f: f.bits.begin),
    )


def _convert_register_field(field: Element, min_bit_offset: int) -> RegisterField:
    # Register fields need to have their bit field adjusted to be relative to
    # the bit offset of the register itself, since originally they are
    # relative to the base of the memory map
    description = field["description"]
    bit_range = field["bitRange"]
    bits = BitFieldRange(
        begin=bit_range["base"] - min_bit_offset,
        end=bit_range["base"] + bit_range["size"] - min_bit_offset,
    )
    return RegisterField(
        bits=bits,
        name=description["name"],
        attr=_convert_access_type(description["access"]),
        reset=description.get("resetValue", None),
        description=description["description"],
    )


def _convert_access_type(access: Element) -> RegisterField.Attr:
    concrete_type = access["_types"][0]
    return {"R": RegisterField.Attr.RO, "W": RegisterField.Attr.WO, "RW": RegisterField.Attr.RW}[
        concrete_type
    ]


def _get_grouped_fields(
    raw_register_fields: t.Sequence[Element], raw_groups: t.Sequence[Element]
) -> t.Mapping[str, t.Tuple[t.Sequence[Element], t.Optional[Element]]]:
    # The object model representation of register maps doesn't have the notion
    # of "a register is made up of register fields". Instead register fields
    # may be annotated with a "group". A "group" may represent a fixed width
    # register (e.g. a 32-bit register), or it may be an arbitrary-length array
    # of data structures that are of the same type (e.g. all the priority bits
    # in the PLIC). If there is an explicitly-annotated group, we use it,
    # otherwise we assign a RegisterField with no group to its own group.

    field_by_group = [
        (group, list(fields))
        for group, fields in sorted_groupby(raw_register_fields, key=_get_group)
    ]

    # Remove groups that are just called "reserved"
    fields_by_group_name = {
        group: fields for group, fields in field_by_group if group != _OBJECT_MODEL_RESERVED_FIELD
    }
    non_blank_groups = [group for group in raw_groups if group["name"] and group.get("description")]

    groups_by_group_name = {group["name"]: group for group in non_blank_groups}

    group_names = fields_by_group_name.keys() | groups_by_group_name.keys()
    return {
        group_name: (
            fields_by_group_name.get(group_name, []),
            groups_by_group_name.get(group_name, None),
        )
        for group_name in group_names
    }


def find_overlapping_intervals(intervals: t.List[Interval]) -> t.List[Interval]:
    """
    Return any (but possibly not all) overlapping intervals.
    """
    tree = IntervalTree(intervals)
    for interval in tree:
        overlaps = tree.search(interval)
        if len(overlaps) > 1:
            return overlaps
    return []


def _validate_registers(registers: t.Sequence[Register]) -> None:
    # Check that no registers overlap
    register_intervals = IntervalTree.from_tuples(
        [(register.byte_range[0], register.byte_range[1], register) for register in registers]
    )
    overlaps = find_overlapping_intervals(register_intervals)
    if overlaps:
        description = "\n".join(f"- {overlap.data.name}" for overlap in overlaps)
        raise ValueError(f"Overlapping registers:\n{description}")


def load_register_map_from_object_model(register_map: t.Mapping) -> RegisterMap:
    raw_register_fields = register_map["registerFields"]
    raw_groups = register_map["groups"]

    grouped_fields = _get_grouped_fields(raw_register_fields, raw_groups)

    # Now that the registers are grouped, build up the registers.
    registers = [
        _create_register(group_name=group_name, group=group, fields=fields)
        for group_name, (fields, group) in grouped_fields.items()
    ]
    _validate_registers(registers)
    return RegisterMap(sorted(registers, key=lambda x: x.byte_offset))

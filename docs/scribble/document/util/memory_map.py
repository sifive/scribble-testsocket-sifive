# Copyright 2019 SiFive, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You should have received a copy of LICENSE.Apache2 along with
# this software. If not, you may obtain a copy at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#################################################################
#
# Classes and functions for working with memory maps.
# These routines are factored into three groups"
#   - Representing and working with memory maps
#   - Creating a displayable MemoryMapTable from memory maps
#   - Building memory maps from ObjectModel design elements.
#
# This factoring allows the code to be reused for multiple purposes.
# For example, they can
#   - Provide an overall memory map of a core complex.
#   - Verify multiple TIMs are or are not contiguous.
#   - Provide detailed memory maps of specific components.
#   - Provide a deterministic ordering of devices (by base address ...)
#
#################################################################
import sys
from typing import Iterable, List, NamedTuple, TypeVar, Tuple
from scribble.model import Element, DocumentException, n_bytes, hex_addr, QueryStream
from scribble.template import human_size
import scribble.table as table


#################################################################
#
# The following classes define the elements of an AddressMap.
#
#  We then define three instances of an AddressMap
#     RangeMap - contains only the address ranges.
#     RegionMap - adds permissions and a description for a range of memory (or memory mapped regs)
#     SectionMap - only adds a note.
#
# The basic idea is to abstract out the address range handling.
# If additional information is needed, extra fields can be added to a subtype of AddressRange.
#
################################################################
class AddressRange(NamedTuple):
    base: int
    size: int

    @property
    def top(self) -> int:
        """Exclusive upper bound of address range."""
        return self.base + self.size - 1


# Specialize the Address Range to include permissions and a description.
#  Used by scribble to describe each address range in detail.
class MemoryRange(NamedTuple, AddressRange):
    base: int
    size: int
    description: str
    readable: bool
    writeable: bool
    executable: bool
    cacheable: bool
    atomics: bool

    @property
    def top(self):
        return self.base + self.size - 1


# Specialise the Address Map to contain a note describing the address range.
#   This is used by scribble to give a general overview of the addresses.
class SectionRange(NamedTuple, AddressRange):
    base: int
    size: int
    notes: str

    @property
    def top(self):
        return self.base + self.size - 1


# Type variable representing a sub-type of AddressRange
R = TypeVar("R", bound=AddressRange)


class AddressMap(List[R]):
    """
    Creates a address map from a collection of address range elements.
    """

    def __init__(self, ranges: Iterable[R]):

        # Sort the ranges by base address.
        sorted_ranges = sorted(ranges, key=lambda region: region.base)
        super().__init__(sorted_ranges)

        # Verify we have no overlapping regions.
        self.assert_no_overlapping_ranges()

    def is_contiguous(self) -> bool:
        regions = self
        for i in range(1, len(regions)):
            if regions[i - 1].top + 1 != regions[i].base:
                return False
        return True

    @property
    def address_range(self) -> AddressRange:
        if self.is_empty():
            return AddressRange(0, 0)
        else:
            return AddressRange(self[0].base, self[-1].top)

    def total_size(self) -> int:
        return sum(region.size for region in self)

    def is_empty(self) -> bool:
        return not self

    def assert_no_overlapping_ranges(self):
        """
        Verify none of the regions overlap
        :param regions: ordered list of memory regions with "range" added in.
        """
        regions = self
        for i in range(1, len(regions)):
            if regions[i - 1].top >= regions[i].base:
                raise DocumentException(
                    f"Memory Regions {regions[i-1]} and " f"{regions[i]} overlap"
                )


# Specialize the maps based on the subtypes of AddressRange.
RegionMap = AddressMap[MemoryRange]
SectionMap = AddressMap[SectionRange]


# Type variables representing sub-types of AddressRange.
R1 = TypeVar("R1", bound=AddressRange)
R2 = TypeVar("R2", bound=AddressRange)


def correlate_maps(
    smaller: AddressMap[R1], bigger: AddressMap[R2]
) -> Iterable[Tuple[List[R1], R2]]:
    """
    Correlate the regions of one map within the regions of the second map.
      Raise error if any of the former don't fit entirely within the second.
    """
    # Start with the first of the smaller regions.
    small_iter = iter(smaller)
    small = next(small_iter, None)

    # For each of the big regions
    for big in bigger:

        # Accumulate group of smaller regions which fit inside the big region
        group = []
        while small is not None and small.top <= big.top and small.base >= big.base:
            group.append(small)
            small = next(small_iter, None)

        # Yield the group of small regions which fit within the big region.
        yield (group, big)

    # If we reach the end and still have smaller regions, then the smaller region didn't fit.
    if small is not None:
        raise DocumentException(f"correlate_maps: Address Range {small} does't fit into section")


###############################################################################
#
# Routines for creating a displayable MemorySectionTable from memory map data structures.
#
################################################################################


class MemorySectionTable(table.Table):
    def __init__(self, title: str, regions: RegionMap, reference_id: str, sections: SectionMap):
        """
        Construct a memory map table based on a detailed memory map and a section overview map.

        :param title: The title of the table.
        :param regions: detailed memory mapped regions
        :param reference_id: reference id of the table.
        :param sections: overview sections for summarizing the detailed regions.
        :return: a displayable asciidoc table.
        """

        # If a single overview section with no notes, then don't show notes column.
        show_notes = len(sections) > 1 or sections[0].notes

        header = [
            table.HeaderCell("Base", halign=table.HAlign.RIGHT, style=table.Style.MONOSPACED),
            table.HeaderCell("Top", halign=table.HAlign.RIGHT, style=table.Style.MONOSPACED),
            table.HeaderCell("Attr.", style=table.Style.MONOSPACED),
            table.HeaderCell("Description"),
        ] + ([table.HeaderCell("Notes")] if show_notes else [])

        # Group the memory regions by corresponding sections.
        regions_by_section = correlate_maps(regions, sections)
        regions_by_section = list(regions_by_section)

        # For each section, format a set memory map rows.
        padding = n_bytes(sections[-1].top)  # How many bytes to display in addresses.
        rows = [
            row
            for regs, section in regions_by_section
            for row in _get_table_rows_for_section(section, regs, show_notes, padding)
        ]

        super().__init__(
            title=title, reference_id=reference_id, header=header, autowidth=True, rows=rows
        )


def _get_table_rows_for_section(
    section: SectionRange, regions: List[MemoryRange], show_notes: bool, padding: int
) -> Iterable[table.Row]:
    """
    Return Row objects for each section.

    The last column spans all rows within the section, so the first row
    will have an additional column.
    """

    # get list of strings for each table row.
    rows = list(get_region_rows(regions, section.base, section.top, padding))

    # Add a note to first row which spans all the rows in this section.
    if show_notes:
        rows[0].append(
            table.Cell(contents=section.notes, row_span=len(rows), valign=table.VAlign.MIDDLE)
        )

    return map(table.Row, rows)


def get_region_rows(
    regions: List[MemoryRange], base: int, top: int, padding: int
) -> Iterable[List[str]]:
    """
    Generate a sequence of memory table rows, spanning from base to top. Fill gaps with "Reserved".
    """
    # for each region in the section
    for region in regions:

        # if there is a gap, create a reserved row.
        if base < region.base:
            yield [hex_addr(base, padding), hex_addr(region.base - 1, padding), "", "Reserved"]

        # create a row for the region
        yield [
            hex_addr(region.base, padding),
            hex_addr(region.top, padding),
            format_permission(region),
            region.description,
        ]

        # Move to the next region.
        base = region.top + 1

    # If there is a gap at the end, another reserved region.
    if base <= top:
        yield [hex_addr(base, padding), hex_addr(top, padding), "", "Reserved"]


def format_permission(region: MemoryRange) -> str:
    NBSP = "&nbsp;"
    return "".join(
        [
            "R" if region.readable else NBSP,
            "W" if region.writeable else NBSP,
            "X" if region.executable else NBSP,
            "C" if region.cacheable else NBSP,
            "A" if region.atomics else NBSP,
        ]
    )


###########################################################################
#
# Routines to build memory maps (and tables) from Object Model design elements.
#
##############################################################################


class MemoryTable(MemorySectionTable):
    """
    Given a group of design elements, construct a memory map table from their memory ranges.
    """

    def __init__(
        self, title: str, elements: Iterable[Element], reference_id: str, sections: Element = None
    ):

        regions = MemoryMap(*elements)
        sectionMap = get_section_map(sections, regions)

        super().__init__(title, regions, reference_id, sectionMap)


class MemoryMap(RegionMap):
    """
    Build a map of all the memory regions contained in a set of elements.
    """

    def __init__(self, *elements: Element):

        # Get all the memory regions for the elements and create a Memory map.
        regions = [
            region
            for element in elements
            for device in element.query().contains_key("memoryRegions")
            for region in getRegions(device)
        ]
        super().__init__(regions)


def getRegions(e: Element) -> Iterable[MemoryRange]:
    """
    Given a design element, get the memory regions corresponding to the element.
    """

    # For each of the element's memory regions
    for region in e.memoryRegions:

        # For each contiguous range of the region
        for range in getRanges(region):

            # Get a description of the memory region.
            # If a single region, give priority to the element's name.
            # TODO: Let's have the description be a more useful description, and make it optional.
            # TODO:   then this could would test for it first rather than last.
            if len(e.memoryRegions) == 1:
                description = e.documentationName or e.name or region.name or region.description
            else:
                description = region.name or region.description

            # For certain types of elements, add the region size to the description.
            if e.is_instance("Port", "Memory", "TIM", "DTIM"):
                description += f" ({human_size(range.size)})"

            # yield a memory range object
            yield MemoryRange(
                base=range.base,
                size=range.size,
                description=description,
                readable=bool(region.permissions.readable),
                writeable=bool(region.permissions.writeable),
                executable=bool(region.permissions.executable),
                cacheable=bool(region.permissions.cacheable),
                atomics=bool(region.permissions.atomics),
            )


def getRanges(memoryRegion: Element) -> Iterable[AddressRange]:
    """
    Calculate the address range of an ObjectModel memory region.
      Throws exception if the resulting range is not contiguous.
    """
    # A memory region consists of a set of (addr, mask) "address sets"
    #   which work together to select a specific range of addresses.

    # Sort the address sets by their base address.
    addressSets = QueryStream(memoryRegion.addressSets).sorted_by("base").collect()
    if not addressSets:
        return

    # Ensure the address sets meet our standards.
    #   We are looking for a solid mask of the form  2^^n - 1.
    #   which doesn't overlap the address bits.
    #   Allows us to treat "mask" as "size-1".
    for addressSet in addressSets:
        if (not low_bits_only(addressSet.mask)) or (addressSet.base & addressSet.mask) != 0:
            raise DocumentException(
                f"Address set too complex: base={addressSet.base:x} mask={addressSet.mask:x}"
            )

    # Start with the first address set
    base = addressSets[0].base
    top = base + addressSets[0].mask

    # For each subsequent address set
    for cur in addressSets[1:]:

        # if there is a gap, then end of contiguous section
        if top + 1 < cur.base:
            yield AddressRange(base, top - base + 1)
            base = cur.base

        # Advance top to be the top of the set
        #  Note: top must never decrease, which could happen if one address set encompasses another.
        top = max(top, cur.base + cur.mask)

    # End of sets - yield last one
    yield AddressRange(base, top - base + 1)


def low_bits_only(mask: int) -> bool:
    """
    verify the mask consists of "0" bits followed by "1" bits.
    TODO: can be done O(c) with subtraction and "&"
    """

    # Python ints are unlimited so we don't need negatives.
    assert mask >= 0

    # Search for the rightmost zero bit.
    while (mask & 1) != 0:
        mask >>= 1

    # if remaining bits are also zero, then mask is zeros followed by all ones.
    return mask == 0


def get_section_map(section_map: Element, regions: RegionMap) -> SectionMap:
    """
    Get an overview of memory sections from the document configuration (or design).
    If none provided, create a dummy section as a placeholder.
    """

    # If we are given a section map, then copy it over.
    if section_map:
        sections = [SectionRange(s.base, s.size, s.notes) for s in section_map]
        section_map = SectionMap(sections)

    # Otherwise, create a default section which covers all the addresses.
    else:
        high_addr = regions[-1].top
        bytes = n_bytes(high_addr)
        size = 1 << (bytes * 8)
        section_map = SectionMap([SectionRange(0, size, "")])

    return section_map


def memory_order(dev: Element):
    """
    Sort key for ordering devices. Preferably by address, then by type.
    """
    key = (base_address(dev), dev._type)
    return key


def base_address(dev: Element) -> int:
    """
    Calculate the base address (of the lowest mapped region) for a device.
       Returns a large address if base address can't be determined,
       placing these devices at the end of sorted lists.
    """
    base = MemoryMap(dev).address_range.base or sys.maxsize
    return base

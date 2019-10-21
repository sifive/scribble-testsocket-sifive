from __future__ import annotations

import typing as t

from scribble import table
from .models import Register, RegisterField, RegisterMap


def get_register_map_table(
    register_map: RegisterMap, caption: str, reference_id: str
) -> table.Table:
    """
    Construct a table.Table for describing a register memory map.

    Args:
        caption: Caption of the table.
        reference_id: An identifier that can be used for cross references
            in the document.
    """
    max_offset_chars = max([len(f"{r.byte_range[0]:X}") for r in register_map.registers])
    return table.Table(
        header=[
            table.HeaderCell("Offset", halign=table.HAlign.RIGHT, style=table.Style.MONOSPACED),
            table.HeaderCell("Name", style=table.Style.MONOSPACED),
            table.HeaderCell("Description"),
        ],
        rows=[
            table.Row(
                [
                    table.Cell(f"0x{r.byte_range[0]:0{max_offset_chars}_X}"),
                    table.Cell(r.name, style=table.Style.DEFAULT if r.is_reserved() else None),
                    table.Cell(r.description),
                ]
            )
            for r in register_map.registers
        ],
        title=caption,
        reference_id=reference_id,
        autowidth=True,
        roles=["sifive-wide-caption"],
    )


def _get_register_field_table_header(description: str, byte_offset: int) -> t.List[table.Row]:
    return [
        # Rows describing the whole register at the top of the table
        table.Row([table.Cell(description, col_span=5, style=table.Style.HEADER)]),
        table.Row(
            [
                table.Cell("Register Offset", col_span=2, style=table.Style.HEADER),
                table.Cell(f"0x{byte_offset:0X}", col_span=3, style=table.Style.MONOSPACED),
            ]
        ),
        table.Row(
            [
                table.Cell(name, style=table.Style.HEADER)
                for name in ["Bits", "Field Name", "Attr.", "Rst.", "Description"]
            ]
        ),
    ]


def _get_register_field_table_row(field: RegisterField) -> table.Row:
    return table.Row(
        [
            table.Cell(field.bits.as_verilog_range(), halign=table.HAlign.CENTER),
            table.Cell(
                "Reserved" if field.is_reserved() else field.name,
                style=table.Style.DEFAULT if field.is_reserved() else table.Style.MONOSPACED,
            ),
            table.Cell(
                "" if field.is_reserved() else field.attr.value, style=table.Style.MONOSPACED
            ),
            table.Cell(
                (
                    ""
                    if field.is_reserved()
                    else "X"
                    if field.reset is None
                    else f"0x{field.reset:X}"
                ),
                style=table.Style.MONOSPACED,
                halign=table.HAlign.RIGHT,
            ),
            table.Cell(field.description, style=table.Style.ASCIIDOC),
        ]
    )


def get_register_field_table(register: Register, reference_id: str) -> table.Table:
    header = _get_register_field_table_header(
        description=f"{register.name} Register Fields", byte_offset=register.byte_offset
    )
    body = [_get_register_field_table_row(field) for field in register.fields]
    return table.Table(
        rows=header + body,
        title=f"`{register.name}`: {register.description} ",
        reference_id=reference_id,
        autowidth=True,
        roles=["sifive-wide-caption"],
    )
